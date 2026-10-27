"""Standard-library HTTPS clients; credentials are read only from runtime variables."""
import json
import os
import requests
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class ModelError(RuntimeError):
    pass


class JSONModel:
    def __init__(self):
        self.provider = os.getenv('TAM_LLM_PROVIDER', 'gemini')
        defaults = {'gemini':'gemini-3.1-flash-lite', 'openai':'gpt-4.1-mini', 'anthropic':'claude-sonnet-4-5', 'ollama':'qwen2.5:7b'}
        if self.provider not in defaults:
            raise ModelError('TAM_LLM_PROVIDER must be gemini, openai, anthropic, or ollama')
        self.model = os.getenv('TAM_MODEL', defaults[self.provider])
        key_names = {'gemini':'GEMINI_API_KEY', 'openai':'OPENAI_API_KEY', 'anthropic':'ANTHROPIC_API_KEY'}
        self.key = os.getenv(key_names.get(self.provider, 'TAM_API_KEY')) or os.getenv('TAM_API_KEY')
        if self.provider != 'ollama' and not self.key:
            raise ModelError('Missing model credential: configure the provider API key securely in environment settings')

    def __call__(self, messages):
        if self.provider == 'gemini':
            if not self.model.replace('-', '').replace('.', '').replace('_', '').isalnum():
                raise ModelError('Invalid Gemini model name')
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
            contents = [{'role':'model' if m['role']=='assistant' else 'user',
                         'parts':[{'text':m['content']}]} for m in messages[1:]]
            from .schema import TriageOutput
            from .tools import TOOL_PARAMETERS
            output_schema = TriageOutput.model_json_schema()
            definitions = output_schema.pop('$defs', {})
            output_schema['properties'].pop('reasoning_trace')
            output_schema['required'].remove('reasoning_trace')
            variants = []
            for name, (params, required) in TOOL_PARAMETERS.items():
                variants.append({'type':'object', 'properties':{
                    'summary':{'type':'string'}, 'action':{'type':'string', 'enum':[name]},
                    'input':{'type':'object', 'properties':{k:{'type':v} for k,v in params.items()},
                             'required':required, 'additionalProperties':False}},
                    'required':['summary','action','input'], 'additionalProperties':False})
            variants.append({'type':'object', 'properties':{
                'summary':{'type':'string'}, 'action':{'type':'string', 'enum':['finish']},
                'output':output_schema}, 'required':['summary','action','output'], 'additionalProperties':False})
            envelope = {'$defs':definitions, 'anyOf':variants}
            payload = {'systemInstruction':{'parts':[{'text':messages[0]['content']}]},
                       'contents':contents, 'generationConfig':{'responseMimeType':'application/json', 'responseJsonSchema':envelope, 'maxOutputTokens':8192}}
            try:
                for attempt in range(5):
                    try:
                        response = requests.post(url, json=payload,
                                                 headers={'x-goog-api-key':self.key}, timeout=60)
                    except requests.Timeout:
                        if attempt == 4:
                            raise
                        time.sleep(2 ** attempt)
                        continue
                    if response.status_code not in {429, 500, 502, 503, 504} or attempt == 4:
                        break
                    retry_after = response.headers.get('Retry-After', '')
                    delay = min(45, max(1, int(retry_after))) if retry_after.isdigit() else (20 if response.status_code == 429 else 2 ** attempt)
                    time.sleep(delay)
                if response.status_code != 200:
                    try:
                        message = response.json().get('error', {}).get('message', '')
                    except (ValueError, AttributeError):
                        message = ''
                    if not isinstance(message, str):
                        message = ''
                    message = message.replace(self.key, '[REDACTED]')
                    raise ModelError(
                        f'gemini returned HTTP {response.status_code}: {message}'
                    )
                data = response.json()
                parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                content = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
                if not content:
                    raise ModelError('Gemini returned no text; check model availability or safety outcome')
                return json.loads(content)
            except requests.RequestException:
                raise ModelError('gemini connection failed') from None
        headers = {'Content-Type':'application/json'}
        if self.provider=='anthropic':
            url = 'https://api.anthropic.com/v1/messages'
            headers.update({'x-api-key':self.key, 'anthropic-version':'2023-06-01'})
            payload = dict(model=self.model, max_tokens=6000, system=messages[0]['content'], messages=messages[1:])
        elif self.provider=='ollama':
            url = os.getenv('TAM_OLLAMA_URL','http://localhost:11434').rstrip('/')+'/api/chat'
            payload = dict(model=self.model, messages=messages, stream=False, format='json')
        else:
            url = 'https://api.openai.com/v1/chat/completions'
            headers['Authorization'] = 'Bearer '+self.key
            payload = dict(model=self.model, messages=messages, response_format={'type':'json_object'})
        try:
            with urlopen(Request(url, data=json.dumps(payload).encode(), headers=headers), timeout=120) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise ModelError(f'{self.provider} returned HTTP {exc.code}') from None
        except (URLError, TimeoutError):
            raise ModelError(f'{self.provider} connection failed') from None
        if self.provider=='anthropic':
            content = ''.join(c.get('text','') for c in data['content'])
        elif self.provider=='ollama':
            content = data['message']['content']
        else:
            content = data['choices'][0]['message']['content']
        return json.loads(content)
