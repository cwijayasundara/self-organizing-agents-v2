from concurrent.futures import ThreadPoolExecutor
import pytest
from agora_v2.ledger import Ledger
from agora_v2.budget import Budget, BudgetExhausted, AccountingError
from agora_v2.mission import Limits


def test_reserve_concurrently_preserves_review_allowance(tmp_path):
    db=tmp_path/'db'
    Ledger(db).close()
    def reserve(_):
        with Ledger(db) as l:
            try:
                return Budget(l,Limits()).reserve('p','exploration',400000)
            except BudgetExhausted:
                return None
    with ThreadPoolExecutor(3) as pool:
        results=list(pool.map(reserve,range(3)))
    assert sum(r is not None for r in results)==2
    with Ledger(db) as l:
        budget=Budget(l,Limits())
        with pytest.raises(BudgetExhausted):
            budget.reserve('p','exploration',1)
        budget.reserve('p','review',200000)
        assert budget.totals()=={'settled_micro':0,'unresolved_micro':1000000,'calls':3}
        with pytest.raises(BudgetExhausted):
            budget.reserve('p','review',1)


def test_settlement_idempotency_unknown_usage_and_overrun(tmp_path):
    with Ledger(tmp_path/'db') as l:
        b=Budget(l,Limits(model_calls=2))
        ident=b.reserve('p','review',100)
        b.settle(ident,80,{'input_tokens':3,'output_tokens':5})
        b.settle(ident,80,{'input_tokens':3,'output_tokens':5})
        with pytest.raises(AccountingError):
            b.settle(ident,79,{})
        second=b.reserve('p','review',100)
        with pytest.raises(AccountingError):
            b.settle(second,200,{})
        assert b.totals()['settled_micro']==280
        with pytest.raises(BudgetExhausted):
            b.reserve('p','review',1)
