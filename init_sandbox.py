"""Create local fictional fixtures and empty knowledge indexes; never overwrite local data."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).parent

def initialize():
    data=ROOT/'data';data.mkdir(exist_ok=True)
    for source in (ROOT/'sample_data').glob('*.json'):
        if not (data/source.name).exists():shutil.copy2(source,data/source.name)
    if not (data/'source_catalog.json').exists():(data/'source_catalog.json').write_text('[]',encoding='utf-8')
    library=ROOT/'library-review';library.mkdir(exist_ok=True)
    for name in ['proposed_guidance.json','source_inventory.json','dialogflow_verified.json','page_index.json']:
        if not (library/name).exists():(library/name).write_text('[]',encoding='utf-8')
    print('Local fictional fixtures initialized. Proprietary product knowledge is not included.')
if __name__=='__main__':initialize()
