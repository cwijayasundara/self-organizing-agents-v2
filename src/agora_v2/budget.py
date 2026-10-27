import json
import uuid
from decimal import Decimal, ROUND_FLOOR


class BudgetExhausted(RuntimeError):
    pass


class AccountingError(RuntimeError):
    pass


class Budget:
    def __init__(self, ledger, limits):
        self.ledger = ledger
        self.limits = limits
        self.cap = int(Decimal(str(limits.budget_usd)) * 1000000)
        self.exploration_cap = int((Decimal(self.cap)*Decimal('.8')).to_integral_value(rounding=ROUND_FLOOR))

    def totals(self):
        row = self.ledger.db.execute('SELECT COALESCE(SUM(settled),0),COALESCE(SUM(CASE WHEN settled IS NULL THEN reserved ELSE 0 END),0),COUNT(*) FROM calls').fetchone()
        return dict(zip(('settled_micro','unresolved_micro','calls'), row))

    def available(self):
        totals = self.totals()
        # Admission is exploration: it cannot consume the review allowance.
        return max(0, min(self.cap - totals['settled_micro'] - totals['unresolved_micro'], self.exploration_cap - self._exploration()))

    def _exploration(self):
        return self.ledger.db.execute("SELECT COALESCE(SUM(COALESCE(settled,reserved)),0) FROM calls WHERE purpose='exploration'").fetchone()[0]

    def reserve(self, peer: str, purpose: str, amount: int) -> str:
        if purpose not in ('exploration','review','finalization') or type(amount) is not int or amount <= 0:
            raise AccountingError('invalid reservation')
        l = self.ledger
        with l.transaction():
            totals = self.totals()
            if l.closed or totals['calls'] >= self.limits.model_calls:
                raise BudgetExhausted('dispatch closed or call limit reached')
            if totals['settled_micro'] + totals['unresolved_micro'] + amount > self.cap:
                raise BudgetExhausted('total model budget exhausted')
            if purpose == 'exploration' and self._exploration() + amount > self.exploration_cap:
                raise BudgetExhausted('review/finalization allowance protected')
            # Enforce admitted helper lifetime allowance; no replacement resets the run budget.
            for event in l.db.execute("SELECT payload FROM events WHERE actor=? AND type='peer_joined'", (peer,)):
                cap = json.loads(event[0]).get('budget_micro')
                spent = l.db.execute('SELECT COALESCE(SUM(COALESCE(settled,reserved)),0) FROM calls WHERE peer=?', (peer,)).fetchone()[0]
                if cap is not None and spent + amount > cap:
                    raise BudgetExhausted('helper lifetime allowance exhausted')
            ident = uuid.uuid4().hex
            l.db.execute("INSERT INTO calls(id,peer,purpose,reserved,state) VALUES(?,?,?,?,'reserved')", (ident, peer, purpose, amount))
            l.event(peer,'call_reserved',{'call_id':ident,'purpose':purpose,'reserved_micro':amount})
            return ident

    def submitted(self, ident):
        with self.ledger.transaction():
            self.ledger.db.execute("UPDATE calls SET state='submitted' WHERE id=? AND state='reserved'", (ident,))
            self.ledger.event('gateway','call_submitted',{'call_id':ident})

    def unresolved(self, ident, reason):
        with self.ledger.transaction():
            row=self.ledger.db.execute('SELECT settled FROM calls WHERE id=?',(ident,)).fetchone()
            if row is not None and row['settled'] is not None:
                self.ledger.event('gateway','call_failed_after_settlement',{'call_id':ident,'reason':reason})
                return
            self.ledger.db.execute("UPDATE calls SET state='unresolved' WHERE id=? AND settled IS NULL", (ident,))
            self.ledger.event('gateway','call_unresolved',{'call_id':ident,'reason':reason})

    def settle(self, ident: str, actual: int, usage: dict):
        if type(actual) is not int or actual < 0:
            raise AccountingError('invalid usage cost')
        overrun = False
        with self.ledger.transaction():
            row = self.ledger.db.execute('SELECT * FROM calls WHERE id=?', (ident,)).fetchone()
            if row is None:
                raise AccountingError('unknown reservation')
            if row['settled'] is not None:
                if row['settled'] != actual or json.loads(row['usage']) != usage:
                    raise AccountingError('conflicting settlement')
                return
            overrun = actual > row['reserved']
            self.ledger.db.execute('UPDATE calls SET settled=?,state=?,usage=? WHERE id=?', (actual,'accounting_error' if overrun else 'settled',json.dumps(usage),ident))
            self.ledger.event('gateway','call_settled',{'call_id':ident,'settled_micro':actual,'overrun':overrun,'usage':usage})
        if overrun:
            raise AccountingError('usage exceeds reservation')
