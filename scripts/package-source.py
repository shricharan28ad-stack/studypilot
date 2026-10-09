from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root=Path(__file__).resolve().parent.parent
out=root/'public'/'studypilot-source.zip'
exclude={'node_modules','dist','.git','.venv','__pycache__','.pytest_cache','.openai','public','data'}
with ZipFile(out,'w',ZIP_DEFLATED) as z:
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if not p.is_file() or any(part in exclude for part in rel.parts): continue
        if p.name in {'.env','.env.local'} or p.suffix in {'.pyc','.tsbuildinfo'}: continue
        z.write(p,Path('studypilot')/rel)
print(out)
