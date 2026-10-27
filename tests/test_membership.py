import pytest
from agora_v2.ledger import Ledger, TaskSpec
from agora_v2.membership import Membership, HelperProposal
from agora_v2.profiles import Profile
from agora_v2.mission import Limits


def team(tmp_path, limits=Limits(), available=lambda: 1000000):
    ledger = Ledger(tmp_path/'db')
    profiles = {'one': Profile('one','one',('general','arithmetic')), 'two': Profile('two','two',('general','arithmetic'))}
    members = Membership(ledger, profiles, limits, available)
    members.bootstrap(['one','two','one'])
    task = ledger.propose_task(TaskSpec('cost','compute',{},('cost_model.csv',),('checked',)))
    return ledger,members,task


def proposal(task):
    return HelperProposal('p1','arithmetic',(task.id,), 'two',100000,('cost_model.csv',),'Recompute a separately discovered cost discrepancy')


def test_independent_admission_and_retirement(tmp_path):
    ledger,members,t = team(tmp_path)
    p = members.propose(proposal(t))
    with pytest.raises(ValueError):
        members.review(p,'p1',True)
    helper = members.review(p,'p2',True)
    assert helper == 'p4'
    with pytest.raises(ValueError):
        members.propose(proposal(t))
    claim = ledger.claim(t.id,helper,30).claim
    members.retire(helper,'partition complete')
    with pytest.raises(ValueError):
        ledger.publish(claim,'late',[])
    assert ledger.claim(t.id,'p1',30).ok
    assert any(e['type']=='peer_retired' for e in ledger.events())
    with pytest.raises(ValueError):
        members.retire('p1','holding work')
    with pytest.raises(ValueError):
        members.retire('p2','only other family')
    ledger.close()


def test_capacity_identity_churn_and_funds(tmp_path):
    ledger,members,t = team(tmp_path, Limits(total_identities=5))
    for expected in ['p4','p5']:
        p = members.propose(proposal(t))
        helper = members.review(p,'p2',True)
        assert helper == expected
        members.retire(helper,'done')
    p = members.propose(proposal(t))
    with pytest.raises(ValueError,match='identities'):
        members.review(p,'p2',True)
    members.available = lambda: 0
    with pytest.raises(ValueError,match='budget'):
        members.propose(proposal(t))
    ledger.close()


def test_single_family_bootstrap_rejected(tmp_path):
    ledger=Ledger(tmp_path/'db')
    members=Membership(ledger, {'one':Profile('one','one',('general',))},Limits())
    with pytest.raises(ValueError):
        members.bootstrap(['one','one','one'])
    assert not ledger.db.execute('SELECT 1 FROM peers').fetchone()
    ledger.close()
