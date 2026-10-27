import json
from pathlib import Path
import pytest
from agora_v2.business.evidence_review import validate_memo
from agora_v2.evidence import EvidenceStore

FIXTURE=Path(__file__).resolve().parents[1]/'examples/evidence_review'


def test_memo_rejects_missing_citations_nonfinite_and_wrong_keys():
    store=EvidenceStore(FIXTURE/'manifest.json')
    summary={'verdict':'pilot_knowledge_teams','retracted_source':'studies/okafor_lind_2024.md','inflated_claim_source':'flexweek_whitepaper.md','harmed_group':'Customer Support','cost_mismatch_eur':72000}
    def memo(s):
        return 'Recommendation [cost_model.csv].\nRESEARCH_SUMMARY\n```json\n'+json.dumps(s)+'\n```'
    assert validate_memo(memo(summary),store)==[]
    for delta in [{'cost_mismatch_eur':True},{'cost_mismatch_eur':float('inf')},{'extra':1},{'retracted_source':'../gold.json'}]:
        assert validate_memo(memo(summary|delta),store)
    assert validate_memo(memo(summary).replace('[cost_model.csv]','[missing.csv]'),store)
    assert validate_memo(memo(summary).replace('[cost_model.csv]',''),store)
