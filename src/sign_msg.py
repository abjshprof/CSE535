import nacl.encoding
import nacl.signing
import pickle
from defs import Key_Pair

#print ("Generated signed key")

def generate_my_key():
	signing_key = nacl.signing.SigningKey.generate()
	#print ("priv_key", signing_key)
	return signing_key

def generate_signed_msg(msg, signing_key):
	#print("got msg", msg)
	bstream = pickle.dumps(msg)
	signed_msg = signing_key.sign(bstream)
	return signed_msg

def get_public_key_hex(signing_key):
	verify_key = signing_key.verify_key
	verify_key_hex = verify_key.encode(encoder=nacl.encoding.HexEncoder)
	return verify_key_hex

def get_key_pair():
	priv_key = nacl.signing.SigningKey.generate()
	pub_key = priv_key.verify_key
	public_key_hex = pub_key.encode(encoder=nacl.encoding.HexEncoder)
	key_pair = Key_Pair(priv_key, public_key_hex)
	#print ("priv_key", priv_key)
	return key_pair

def gen_invalid_sign_msg(signed_msg):
	signedlist = list(signed_msg)
	signedlist[0] = (signedlist[0] + 1) % 256
	newsigned=bytes(signedlist)
	invalid_signed = nacl.signing.SignedMessage._from_parts(signed_msg._signature, signed_msg._message, newsigned)
	return invalid_signed

