import asyncio
from dataclasses import dataclass
import time
from .budget import BudgetExhausted
from .outcome import OutcomeChecker
from .peer import Peer
from .trace import peer_snapshot,export_run


@dataclass(frozen=True)
class RunResult:
    status: str
    issues: tuple[str,...]
    latency_seconds: float


class Runtime:
    def __init__(self, mission,ledger,membership,gateway,budget,slots,dispatcher,output,mode='live',schedule=None):
        self.mission,self.ledger,self.membership,self.gateway,self.budget,self.slots,self.dispatcher,self.output,self.mode=mission,ledger,membership,gateway,budget,slots,dispatcher,output,mode
        self.context,self.evidence=dispatcher.context,dispatcher.evidence
        self.schedule=schedule
        self.ledger.db.execute("INSERT OR REPLACE INTO meta VALUES('mode',?)",(mode,))
        self.cancelled=asyncio.Event()
        self.peers={}

    def cancel(self):
        self.cancelled.set()

    async def run(self, mission):
        self.mission=mission
        start=time.monotonic()
        status,issues='stalled',[]
        round_index=0
        async def episodes():
            nonlocal status,round_index
            scripted_index=0
            waiting_steps=0
            while not self.cancelled.is_set():
                self.evidence.metadata()  # Hash validation also catches changed/unavailable evidence.
                active=[dict(r) for r in self.ledger.db.execute("SELECT * FROM peers WHERE state NOT IN ('retired','failed','draining') ORDER BY id")]
                if not active:
                    return
                if self.schedule is not None:
                    if scripted_index>=len(self.schedule):
                        return
                    ident=self.schedule[scripted_index]
                    scripted_index+=1
                    selected=next((r for r in active if r['id']==ident),None)
                    if selected is None:
                        raise ValueError('script names inactive peer')
                else:
                    selected=active[round_index%len(active)]
                    round_index+=1
                ident=selected['id']
                if ident not in self.peers:
                    self.peers[ident]=Peer(ident,selected['model_key'],mission,self.gateway,self.dispatcher)
                self.ledger.expire_claims(self.ledger.clock())
                view=peer_snapshot(self.ledger)
                view['scope_version']=self.ledger.scope_version
                view['identity']=ident
                view['events']=self.ledger.events()[-25:]
                for event in view['events']:
                    for key in ('content','reason'):
                        value=event['payload'].get(key)
                        if isinstance(value,str) and len(value)>1000:
                            event['payload'][key]=value[:1000]
                            event['payload'][key+'_truncated']=True
                async with self.slots.enter('peer',ident) as execution:
                    step_result=await self.peers[ident].step(view,execution)
                waiting_steps=waiting_steps+1 if step_result.get('waiting') else 0
                if self.schedule is None and waiting_steps>=2*len(active):
                    status='stalled'
                    return
                candidate=self.ledger.completion_snapshot()
                if candidate:
                    checker=OutcomeChecker(self.ledger,self.evidence,mission,self.gateway,self.slots)
                    decision=await checker.check(candidate)
                    if decision.approved:
                        with self.ledger.transaction():
                            if self.ledger.snapshot_current(candidate):
                                # Atomically close admission at the checked scope version.
                                self.ledger.db.execute("UPDATE meta SET value='1' WHERE key='closed'")
                                status='completed'
                                return
                    else:
                        issues.extend(decision.problems)
                await asyncio.sleep(0)
            status='cancelled'
        try:
            if self.cancelled.is_set():
                status='cancelled'
            else:
                work=asyncio.create_task(episodes())
                stop=asyncio.create_task(self.cancelled.wait())
                try:
                    done,_=await asyncio.wait({work,stop},timeout=mission.limits.wall_seconds,return_when=asyncio.FIRST_COMPLETED)
                    if not done:
                        status='timed_out'
                    elif stop in done:
                        status='cancelled'
                    else:
                        await work
                finally:
                    for pending in (work,stop):
                        if not pending.done():
                            pending.cancel()
                    await asyncio.gather(work,stop,return_exceptions=True)
        except BudgetExhausted as exc:
            status='budget_exhausted'
            issues.append(str(exc))
        except (OSError,ValueError) as exc:
            status='insufficient_evidence' if 'hash' in str(exc) or isinstance(exc,OSError) else 'failed'
            issues.append(str(exc))
        except asyncio.CancelledError:
            status='cancelled'
        except Exception as exc:
            status='failed'
            issues.append(f'{type(exc).__name__}: {exc}')
        finally:
            with self.ledger.transaction():
                self.ledger.db.execute("UPDATE meta SET value='1' WHERE key='closed'")
                self.ledger.event('runtime','shutdown_started',{'status':status})
                for row in self.ledger.db.execute('SELECT id,holder FROM tasks WHERE holder IS NOT NULL').fetchall():
                    self.ledger.db.execute("UPDATE tasks SET state='open',holder=NULL,token=NULL,expires=NULL WHERE id=?",(row['id'],))
                    self.ledger.event(row['holder'],'claim_released',{'task_id':row['id'],'reason':'shutdown'})
                for row in self.ledger.db.execute("SELECT id FROM peers WHERE state NOT IN ('retired','failed')").fetchall():
                    self.ledger.db.execute("UPDATE peers SET state='draining' WHERE id=?",(row['id'],))
                    self.ledger.event(row['id'],'peer_state',{'state':'draining'})
                    self.ledger.db.execute("UPDATE peers SET state='retired' WHERE id=?",(row['id'],))
                    self.ledger.event(row['id'],'peer_retired',{'reason':'run shutdown'})
            if self.dispatcher.executor is not None and hasattr(self.dispatcher.executor,'close'):
                try:
                    await self.dispatcher.executor.close()
                except Exception as exc:
                    issues.append(f'executor cleanup failed: {exc}')
                    status='failed'
            self.ledger.event('runtime','run_finished',{'status':status,'issues':issues,'cost':self.budget.totals()})
            result=RunResult(status,tuple(issues),time.monotonic()-start)
            export_run(self,result)
        return result
