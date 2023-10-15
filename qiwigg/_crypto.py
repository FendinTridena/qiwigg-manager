from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from Cryptodome.Hash import MD5
import base64

_PASSPHRASE = b"ZYP*G-KaPdSgVkYp3s6v9y=v?E(H+TTT"


def bytes_to_key(data, salt, output=48):
    # extended from https://gist.github.com/gsakkis/4546068
    assert len(salt) == 8, len(salt)
    data += salt
    key = MD5.new(data).digest()
    final_key = key
    while len(final_key) < output:
        key = MD5.new(key + data).digest()
        final_key += key
    return final_key[:output]

def encrypt(message):
    salt = Random.new().read(8)
    key_iv = bytes_to_key(_PASSPHRASE, salt, 32+16)
    key = key_iv[:32]
    iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(b"Salted__" + salt + aes.encrypt(pad(message, 16)))

def decrypt(encrypted):
    encrypted = base64.b64decode(encrypted)
    assert encrypted[0:8] == b"Salted__"
    salt = encrypted[8:16]
    key_iv = bytes_to_key(_PASSPHRASE, salt, 32+16)
    key = key_iv[:32]
    iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    return unpad(aes.decrypt(encrypted[16:]), 16)
