from nacl.bindings.utils import sodium_memcmp
import nacl.encoding
import nacl.hash
import pickle

HASHER = nacl.hash.sha256

def validate_integrity(received_msg, dgs1):
	print (len(received_msg))
	msg = nacl.encoding.HexEncoder.decode(received_msg)
	print ("orig", pickle.loads(msg)) 
	dgs0 = HASHER(msg, encoder=nacl.encoding.HexEncoder)
	print ("dgs0", dgs0)
	print ("dgs1", dgs1)
	if sodium_memcmp(dgs0, dgs1):
	    return 1 #'equals'
	return 0 #'is different from'

#MSG = 'Digest of {0} message {1} original digest'

#for chk in (('original', received_msg),
#            ('truncated', shortened),
#            ('modified', modified)):

    #print(MSG.format(chk[0], validate_integrity(chk[1], dgst)))
