"""Inside-out Developer ID signing for a standalone app; no credentials are embedded."""
from pathlib import Path
import argparse
import subprocess

def run(*cmd):subprocess.run([str(p) for p in cmd],check=True)
def sign_app(app,identity=None):
    app=Path(app).resolve()
    if not identity:
        run('codesign','--force','--deep','--sign','-',app)
        return
    if not identity.startswith('Developer ID Application:'):
        raise ValueError('Use an installed Developer ID Application certificate.')
    # Sign every Mach-O before the outer bundle. Never use --deep to sign a release.
    for path in sorted(app.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if not path.is_file() or path.is_symlink():continue
        with path.open('rb') as f:magic=f.read(4)
        if magic in [bytes.fromhex(s) for s in ('cffaedfe','cefaedfe','feedfacf','feedface','cafebabe','bebafeca')]:
            extra=['--entitlements',Path(__file__).with_name('Node.entitlements')] if path.name=='node' else []
            run('codesign','--force','--options','runtime','--timestamp','--sign',identity,*extra,path)
    run('codesign','--force','--options','runtime','--timestamp','--sign',identity,app)
    run('codesign','--verify','--deep','--strict',app)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('app',type=Path);p.add_argument('--identity',required=True);a=p.parse_args();sign_app(a.app,a.identity)
