"""Deterministic offline rehearsal rules, never Jev inference or security guarantees."""
import re

STOPWORDS=set('a an the to do how we i is are for of and in before after what should can with this question passage deployment deploy'.split())

def tokens(text):
    return set(re.findall(r'[a-z0-9]+',text.lower()))-STOPWORDS

def simulate_decision(scenario, text):
    lower=text.lower()
    uncertain=any(word in lower for word in ('unclear','unknown','uncertain','missing evidence','already-dispatched'))
    if scenario=='guardrails':
        unsafe=any(word in lower for word in ('ignore previous','ignore the system','reveal your api','leak the key','extract secrets','delete_repository','drop_database'))
        return {'risk':{'choice':'unsafe' if unsafe else 'safe','confidence':.97}}
    if scenario=='routing':
        tier='large' if len(text)>1000 or 'complex' in lower else 'medium' if any(w in lower for w in ('compare','investigate','latency','plan')) else 'small'
        return {'route':{'choice':tier,'confidence':.94}}
    if scenario=='reranking':
        question,_,passage=text.partition('\nPassage:')
        overlap=len(tokens(question).intersection(tokens(passage)))
        return {'relevance':{'score':min(4,overlap*2),'confidence':.9}}
    if scenario=='evals':
        reference=text.partition('\nReference:')[2].partition('\nAnswer:')[0].strip()
        answer=text.partition('\nAnswer:')[2].strip().removeprefix('According to the runbook: ').strip()
        supported=bool(answer) and answer in reference and 'I do not know' not in answer
        return {'quality':{'score':4 if supported else 1,'confidence':.91},'grounded':{'noul':.95 if supported else .2}}
    if scenario=='confidence':
        return {'action':{'choice':'review' if uncertain else 'proceed','confidence':.55 if uncertain else .96}}
    if scenario=='tools':
        denied=any(w in lower for w in ('delete_repository','drop_database','rotate_prod_secrets','transfer_funds'))
        choice='deny' if denied else 'allow' if any(w in lower for w in ('draft_remediation_issue','read','list')) else 'ask'
        return {'permission':{'choice':choice,'confidence':.96}}
    raise ValueError('Unknown simulator scenario')
