import json
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.skipif(shutil.which('node') is None,reason='Node required for browser reducer regression')
def test_replay_cursor_uses_artifact_version_published_at_that_event():
    app=Path(__file__).resolve().parents[1]/'src/agora_v2/web/app.js'
    script=r'''
const vm=require('node:vm'),fs=require('node:fs');
const context={module:{exports:{}},document:{getElementById:()=>({})},setInterval:()=>0,fetch:()=>new Promise(()=>{})};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const events=[{actor:'system',type:'task_proposed',payload:{task_id:'final',key:'memo',spec:{final:true}}},{actor:'p1',type:'artifact_published',payload:{task_id:'final',artifact_id:'old'}},{actor:'p1',type:'artifact_published',payload:{task_id:'final',artifact_id:'new'}}];
console.log(JSON.stringify(context.module.exports.reduce(events.slice(0,2))));
'''
    result=subprocess.run(['node','-e',script,str(app)],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout).get('memo_artifact_id')=='old'
