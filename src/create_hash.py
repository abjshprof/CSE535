import nacl.encoding
import nacl.hash
import pickle
from collections import namedtuple
from defs import EMsg_Hash
HASHER = nacl.hash.sha256

def create_hash_and_encode_msg(msg): #the msg is a tuple object
	print ("got msg", msg)
	bstream = pickle.dumps(msg)  #we need to convert it to a byte stream first
	encd_msg = nacl.encoding.HexEncoder.encode(bstream)
	digest = HASHER(bstream, encoder=nacl.encoding.HexEncoder)
	emsg_hash = EMsg_Hash(encd_msg, digest)
	#print ("encd_msg\n", emsg_hash.encd_msg)
	#print ("")
	print ("digest\n", emsg_hash.digest)
	return emsg_hash
	

# now send msg and digest to the user
#create_hash_and_encode_msg(msg)
#print(nacl.encoding.HexEncoder.encode(msg))
#print(digest)

