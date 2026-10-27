import json
import re
from ..business.evidence_review import KEYS,parse_summary,validate_memo
from ..evidence import EvidenceStore


def score(result,gold,manifest):
    evidence=EvidenceStore(manifest)
    expected=json.loads(gold.read_text())
    try:
        summary=parse_summary(result.memo)
        if not isinstance(summary,dict):
            summary={}
    except (ValueError,TypeError):
        summary={}
    correct={key:summary.get(key)==expected[key] for key in sorted(KEYS)}
    correct['cost_mismatch_eur']=type(summary.get('cost_mismatch_eur')) in (int,float) and summary['cost_mismatch_eur']==expected['cost_mismatch_eur']
    refs={r.split(':',1)[0] for r in re.findall(r'\[([^\]\n]+)\]',result.memo.split('RESEARCH_SUMMARY')[0])}
    valid=refs & set(evidence.files)
    return {'arm':result.arm,'status':result.status,'mode':result.mode,'field_correct':correct,'business_field_correctness':sum(correct.values())/len(KEYS),
            'evidence_file_coverage':len(valid)/len(evidence.files),'citation_errors':validate_memo(result.memo,evidence),
            'unsupported_claims':result.metrics.get('unsupported_claims'),'unsupported_claims_note':'Independently judged during arm execution' if 'unsupported_claims' in result.metrics else 'Not independently judged by this deterministic export scorer',
            **result.metrics,'metadata':result.metadata,'interpretation':'scripted mechanics only; no live comparison' if result.mode in ('scripted','offline_fake') else ('provider-backed execution; inspect enforcement differences' if 'matched_limits' in result.metadata else 'imported export; enforcement differences must be reviewed')}
