import json
import math
import re

KEYS={'verdict','retracted_source','inflated_claim_source','harmed_group','cost_mismatch_eur'}
VERDICTS={'adopt_company_wide','pilot_knowledge_teams','do_not_adopt'}


def parse_summary(text):
    matches=list(re.finditer(r'RESEARCH_SUMMARY\s*```json\s*(.*?)\s*```\s*$',text,re.S))
    if len(matches)!=1:
        raise ValueError('expected one final fenced RESEARCH_SUMMARY')
    return json.loads(matches[0][1])


def validate_memo(text, evidence):
    problems=[]
    try:
        summary=parse_summary(text)
        if not isinstance(summary,dict) or set(summary)!=KEYS:
            raise ValueError('summary needs exactly five keys')
        if summary['verdict'] not in VERDICTS:
            raise ValueError('invalid verdict')
        number=summary['cost_mismatch_eur']
        if type(number) not in (int,float) or not math.isfinite(number) or number<0:
            raise ValueError('cost mismatch must be finite nonnegative EUR')
        for field in ('retracted_source','inflated_claim_source'):
            evidence.read(summary[field],0,0)
        departments={line.split(',')[0] for line in evidence.read('staff_survey.csv').splitlines()[1:]}
        if summary['harmed_group'] not in departments:
            raise ValueError('unknown department')
    except (ValueError,TypeError,KeyError) as exc:
        problems.append(str(exc))
    body=text.split('RESEARCH_SUMMARY')[0]
    if len(body.split())>=450:
        problems.append('memo must be under 450 words')
    citations=re.findall(r'\[([^\]\n]+)\]',body)
    if not citations:
        problems.append('memo needs evidence citations')
    for ref in citations:
        try:
            evidence.read(ref.split(':',1)[0],0,0)
        except (ValueError,OSError):
            problems.append(f'unresolved citation: {ref}')
    return problems
