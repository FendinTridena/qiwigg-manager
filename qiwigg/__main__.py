import sys
import argparse
import json

from pathlib import Path

from qiwigg import _qiwi, _qiwitypes


def pretty_print_folders(folders):
    parent_to_children = {}
    for folder in folders:
        parent_to_children.setdefault(folder.parent_id, []).append(folder)

    def p(parent, indent=0):
        text_indent = indent * " "
        for folder in parent_to_children.get(parent, []):
            print(f"{text_indent}{folder}")
            p(folder.id, indent + 4)

    p(None)


parser = argparse.ArgumentParser(
    prog="qiwigg",
    description="qiwi.gg manager. Upload, delete, move files; create, delete folders.",
)
parser.add_argument(
    "--version",
    action="version",
    version=f"{_qiwi.NAME} {_qiwi.VERSION}",
)
_action_choices = (
    "upload_files",
    "list_folders",
    "create_folders",
    "delete_folders",
    "list_files",
    "move_files",
    "move_all_files",
    "delete_files",
)
parser.add_argument(
    "-a",
    "--action",
    metavar="action",
    default="upload_files",
    choices=_action_choices,
    help=(
        f"action to perform, defaults to upload; available choices: {_action_choices}"
    ),
)
parser.add_argument(
    "--config",
    metavar="DIR",
    help=(
        "path to config directory - used to store your cookies and credentials; "
        "defaults to ~/.config/qiwigg/"
    ),
)
parser.add_argument(
    "--proxy",
    help="proxy to use for HTTP requests, example: socks5://localhost:1080",
)
parser.add_argument("--email")
parser.add_argument("--password")
parser.add_argument(
    "--no-save-creds",
    action="store_false",
    dest="save_creds",
    help="don't save credentials to file",
)
parser.add_argument(
    "--json",
    action="store_true",
    help="return JSON data",
)
parser.add_argument(
    "--to",
    help=(
        "folder ID, used for following actions as a destination folder: "
        "upload, create_folders, move_files, move_all_files; defaults to main folder"
    ),
)
parser.add_argument(
    "--chunk-size",
    type=int,
    help="chunk size for upload, defaults to 100000000 bytes (100MB)",
)
parser.add_argument("args", nargs="*")

args = parser.parse_args()

if args.config is None:
    args.config = Path.home() / ".config" / "qiwigg"
else:
    args.config = Path(args.config)

creds_file = (args.config / "credentials.txt")
if args.email is None and args.password is None:
    try:
        args.email, args.password = (
            creds_file.read_text(encoding="utf-8").splitlines()[:2]
        )
    except FileNotFoundError:
        pass
elif args.save_creds and args.email is not None and args.password is not None:
    args.config.mkdir(parents=True, exist_ok=True)
    creds_file.write_text(f"{args.email}\n{args.password}", encoding="utf-8")

if args.proxy is not None:
    proxies = {
        "http": args.proxy,
        "https": args.proxy,
    }
else:
    proxies = None

if args.chunk_size is None:
    try:
        chunk_txt = (args.config / "chunk-size.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    else:
        args.chunk_size = int(chunk_txt.splitlines()[0])

qiwi = _qiwi.QiwiGG(args.email, args.password, args.config / "cookies.txt", proxies)

data = None

if args.action == "list_folders":
    data = qiwi.get_folders()
    if not args.json:
        pretty_print_folders(data)
elif args.action == "create_folders":
    if len(args.args) == 0:
        print("Supply at least one folder name as argument!", file=sys.stderr)
        sys.exit(1)
    data = []
    for arg in args.args:
        folder = qiwi.create_folder(arg, args.to)
        data.append(folder)
        if not args.json:
            print(folder)
elif args.action == "delete_folders":
    if len(args.args) == 0:
        print("Supply at least one folder ID as argument!", file=sys.stderr)
        sys.exit(2)
    data = []
    for arg in args.args:
        qiwi.delete_folder(arg)
        data.append(arg)
        if not args.json:
            print(f"{arg} deleted")
elif args.action == "list_files":
    if len(args.args) == 0:
        arg = None
    else:
        arg = args.args[0]
    data = qiwi.get_files(arg)
    if not args.json:
        for file in data:
            print(file)
elif args.action == "move_files":
    if len(args.args) == 0:
        print("Supply at least one file ID as argument!", file=sys.stderr)
        sys.exit(3)
    data = {"moved": []}
    for arg in args.args:
        folder_id = qiwi.move_file(arg, args.to)
        if "to" not in data:
            data["to"] = folder_id
        data["moved"].append(arg)
        if not args.json:
            print(f"{arg} moved")
elif args.action == "move_all_files":
    if len(args.args) == 0:
        print("Supply at least one folder ID as argument!", file=sys.stderr)
        sys.exit(4)
    data = {"moved": []}
    for arg in args.args:
        if arg == args.to:
            continue
        for file in qiwi.get_files(arg):
            folder_id = qiwi.move_file(file, args.to)
            if "to" not in data:
                data["to"] = folder_id
            data["moved"].append(file)
            if not args.json:
                print(f"{file} moved")
elif args.action == "delete_files":
    if len(args.args) == 0:
        print("Supply at least one file ID as argument!", file=sys.stderr)
        sys.exit(5)
    data = []
    for arg in args.args:
        qiwi.delete_file(arg)
        data.append(arg)
        if not args.json:
            print(f"{arg} deleted")
elif args.action == "upload_files":
    if len(args.args) == 0:
        print("Supply at least one file path as argument!", file=sys.stderr)
        sys.exit(6)
    data = []
    for arg in args.args:
        print(f"uploading {arg}", file=sys.stderr)
        file = qiwi.upload_file(arg, chunk_size=args.chunk_size)
        if args.to is not None:
            qiwi.move_file(file, args.to)
        file.path = arg
        data.append(file)
        if not args.json:
            print(f"{file.url} {file.name}")
else:
    raise NotImplementedError(f"{args.action} action is not implemented")

if args.json:
    print(json.dumps(data, indent=4, cls=_qiwitypes.QiwiJSONEncoder))
