from collections import namedtuple
Person = namedtuple('Person', 'first_name last_name zip_code')

##Replica defs
#we need to sign this order statements


#Order_statement = namedtuple('Order_Statement', 'order_tag slot_id replica_id op')

#should Order Proof include the Config
#Order_proof = namedtuple('Order_Proof', 'slot_id replica_id op order_statements')

#we need to sign the result statement

#Result_statement = namedtuple('Result_Statement', 'result_tag op digest')
#Result_proof = namedtuple('Result_Proof', 'slot_id replica_id op result_statements')

#we also need to sign the shuttles?    
#Shuttle = namedtuple('Forward_shuttle', 'is_result order_proof result_proof')

#Result_shuttle = namedtuple('Result_shuttle', 'is_result order_proof result_proof')
#Shuttle_package = namedtuple('Signed_shuttle_package', 'signed_shuttle_tag replica_id signed_shuttle')

#remember, history is a s set of order proofs
#Replica_hist = namedtuple('Replica_history', '')

##Client
#Client_req = namedtuple('Client_request', 'uniq_req_id is_retransmit op')


#Signing
EMsg_Hash = namedtuple('Encoded_Msg_and_Hash_Tuple', 'encd_msg digest')

Key_Pair = namedtuple('Key_Pair', 'priv_key, public_key_hex')
#=====================
#shuttle is a dict where two elements, order_proof & result_proof are dicts themselves
#order_proof, result_proof are dictionaries which have one element, the statements, as a list of dictionaries
#order_statements is a list of dictionaries, each individual element is a dict
