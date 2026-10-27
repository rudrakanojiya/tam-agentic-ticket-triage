import json
import unittest
from unittest.mock import Mock, patch
from tam_agent.llm import JSONModel, ModelError


class GeminiTests(unittest.TestCase):
    @patch.dict('os.environ', {'TAM_LLM_PROVIDER':'gemini', 'GEMINI_API_KEY':'test-only'}, clear=True)
    @patch('tam_agent.llm.requests.post')
    def test_gemini_json_and_roles(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'candidates':[{'content':{'parts':[
            {'text':json.dumps({'summary':'Need evidence', 'action':'search_kb', 'input':{'query':'SLA'}})}]}}]}
        result = JSONModel()([{'role':'system','content':'rules'}, {'role':'user','content':'ticket'},
                              {'role':'assistant','content':'action'}, {'role':'user','content':'observation'}])
        self.assertEqual(result['action'], 'search_kb')
        kwargs = post.call_args.kwargs
        self.assertEqual([m['role'] for m in kwargs['json']['contents']], ['user','model','user'])
        self.assertEqual(kwargs['json']['systemInstruction']['parts'][0]['text'], 'rules')
        self.assertEqual(kwargs['headers']['x-goog-api-key'], 'test-only')
        self.assertNotIn('test-only', post.call_args.args[0])
        variants = kwargs['json']['generationConfig']['responseJsonSchema']['anyOf']
        history = next(v for v in variants if v['properties']['action']['enum']==['search_ticket_history'])
        self.assertIn('query_text', history['properties']['input']['required'])

    @patch.dict('os.environ', {'GEMINI_API_KEY':'test-only'}, clear=True)
    @patch('tam_agent.llm.requests.post')
    def test_error_is_redacted(self, post):
        post.return_value = Mock(status_code=403)
        with self.assertRaisesRegex(ModelError, 'HTTP 403'):
            JSONModel()([{'role':'system','content':'rules'}])

    @patch.dict('os.environ', {'GEMINI_API_KEY':'test-only'}, clear=True)
    @patch('tam_agent.llm.time.sleep')
    @patch('tam_agent.llm.requests.post')
    def test_rate_limit_backoff(self, post, sleep):
        limited = Mock(status_code=429, headers={'Retry-After':'25'})
        success = Mock(status_code=200)
        success.json.return_value = {'candidates':[{'content':{'parts':[{'text':'{"ok":true}'}]}}]}
        post.side_effect = [limited, success]
        self.assertEqual(JSONModel()([{'role':'system','content':'rules'}]), {'ok':True})
        sleep.assert_called_once_with(25)

    @patch.dict('os.environ', {}, clear=True)
    def test_missing_key(self):
        with self.assertRaises(ModelError):
            JSONModel()
