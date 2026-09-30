import os,unittest
from unittest.mock import patch
import chat_service
from chat_model import ModelUnavailable
from init_sandbox import initialize

class PublicCheckoutTests(unittest.TestCase):
 def setUp(self):chat_service.SESSIONS.clear()
 def ask(self,question):return chat_service.chat(dict(message=question,product='QN33',version='',audience='customer',scope='fictional'))
 def test_empty_library_does_not_claim_product_knowledge(self):
  with patch.dict(os.environ,{'CHAT_PROVIDER':'local'}):result=self.ask('What is the warranty period?')
  self.assertEqual(result['response_kind'],'no_relevant_source');self.assertFalse(result['sources'])
 def test_missing_private_replay_source_is_explicit(self):
  with patch.dict(os.environ,{'CHAT_PROVIDER':'local'}),self.assertRaises(ModelUnavailable) as error:self.ask('Can all missing events be replayed?')
  self.assertEqual(error.exception.code,'retrieval_failure')
 def test_real_mode_without_key_does_not_fake_an_answer(self):
  with patch.dict(os.environ,{'CHAT_PROVIDER':'openai','OPENAI_API_KEY':''}),self.assertRaises(ModelUnavailable) as error:self.ask('Help')
  self.assertEqual(error.exception.code,'model_configuration_error')
 def test_no_private_account_override(self):
  from identity_resolution import apply_display_confirmation
  self.assertEqual(apply_display_confirmation('example',{},'Sample customer'),'Sample customer')
if __name__=='__main__':unittest.main()
