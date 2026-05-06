#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate VAPID keys for Web Push (alternative to `npm run vapid`).

Output: prints public/private keys in the base64-url format both
`web-push` (Node) and DN.PUSH_VAPID_PUBLIC_KEY accept.
"""
import base64, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from py_vapid import Vapid01
except ImportError:
    print('Run first: pip install py-vapid')
    sys.exit(1)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# Generate fresh ECDSA P-256 key pair
priv = ec.generate_private_key(ec.SECP256R1())
pub = priv.public_key()

# Encode public key as 65-byte uncompressed point (0x04 + X + Y), base64-url
pub_bytes = pub.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode('ascii')

# Encode private key as 32-byte raw scalar, base64-url
priv_int = priv.private_numbers().private_value
priv_bytes = priv_int.to_bytes(32, 'big')
priv_b64 = base64.urlsafe_b64encode(priv_bytes).rstrip(b'=').decode('ascii')

print('=' * 60)
print('VAPID Keys for Web Push')
print('=' * 60)
print()
print('Public Key (將貼進 blog/blog-shared.js DN.PUSH_VAPID_PUBLIC_KEY')
print('             也貼進 Vercel env var VAPID_PUBLIC_KEY):')
print()
print('  ' + pub_b64)
print()
print('Private Key (只貼進 Vercel env var VAPID_PRIVATE_KEY,絕不公開):')
print()
print('  ' + priv_b64)
print()
print('=' * 60)
print('VAPID_CONTACT 環境變數值: mailto:expertise88864@gmail.com')
print('=' * 60)
