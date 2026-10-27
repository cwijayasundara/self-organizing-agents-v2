from dataclasses import asdict
import json
from pathlib import Path
from .arms import ARMS,ExportArm
from .contracts import EvaluationInput
from .score import score
from ..mission import load_mission
from ..evidence import EvidenceStore


async def evaluate(config_path: Path,output: Path):
    config_path=Path(config_path).resolve()
    config=json.loads(config_path.read_text())
    def resolve(path):return (config_path.parent/path).resolve()
    mission=load_mission(resolve(config['mission']))
    gold=resolve(config['gold'])
    evidence=EvidenceStore(mission.manifest)
    if gold.is_relative_to(evidence.root) or any((evidence.root/ref).resolve()==gold or (evidence.root/ref).samefile(gold) for ref in evidence.files):
        raise ValueError('gold must be outside the evidence room')
    exports=config.get('exports',{})
    if set(exports)-set(ARMS):
        raise ValueError('unknown evaluation arm')
    seeds=config.get('seeds',[0])
    if not isinstance(seeds,list) or not seeds or any(type(s) is not int for s in seeds):
        raise ValueError('seeds must be nonempty integer list')
    if len(seeds)!=1 and exports:
        raise ValueError('one export is one recorded run, not repeated seed executions; evaluate each export separately')
    results=[]
    for seed in seeds:
        inputs=EvaluationInput(mission.brief,mission.rubric,mission.manifest,asdict(mission.limits),seed)
        for name in ARMS:
            arm=ExportArm(name,resolve(exports[name]) if name in exports else None)
            result=await arm.run(inputs) # inputs deliberately exclude gold
            if result.status=='not_run':
                results.append({'arm':name,'status':'not_run','reason':result.metadata['reason']})
            else:
                results.append(score(result,gold,mission.manifest))
    report={'format_version':1,'results':results,'note':'Export scoring only. Missing arms are not simulated, repeats are not fabricated, and scripted results establish no live superiority.'}
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report
