import nacl.signing
import nacl.exceptions
import pickle

def verify_signed_msg(public_key_hex, signed_msg):
	verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
	try:
		bsteam_msg = verify_key.verify(signed_msg)
	except :
		print("caught exception trying to verifu sign")
		return None
	orig_msg = pickle.loads(bsteam_msg)
	return orig_msg
