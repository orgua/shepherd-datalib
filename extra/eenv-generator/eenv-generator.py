#!/bin/env python

import subprocess
import shutil
import click
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime

from on_off_patterns import generate_random_independent

# Dict of generator functions (click commands) and respective metadata
GENERATORS = {
    generate_random_independent: { 
        'data_type': 'iv_trace',
        'description': 'random generated iv-traces with no correlation between nodes'
    }
}

# Generate a mapping from generator names to metadata
GENERATOR_INFO = { fnc.name: GENERATORS[fnc] for fnc in GENERATORS }

IDEAL_VOLTAGE_GAIN = 1e-6 # PRU uses uV
IDEAL_CURRENT_GAIN = 1e-9 # PRU uses nA

@click.group()
@click.option('--node-count', type=click.INT, required=True)
@click.option('--duration', type=click.FLOAT, required=True)
@click.option('--output-dir', '-o', type=click.Path(exists=True, resolve_path=True, writable=True, path_type=Path), default=Path('.'))
@click.option('--name', '-n', type=click.STRING, help='Name of the energy environment. A subfolder with this name will be created in `output-dir`', required=True)
@click.option('--no-git', is_flag=True)
@click.pass_context
def cli(ctx, node_count, duration, output_dir, name, no_git) -> None:
    '''
    CLI entrypoint
    Takes common options and stores them in the click context.
    Also writes metadata regarding the generated energy environment
    to a eenv.yaml file in the output directory.
    '''

    output_dir = output_dir / name

    # Add common parameters to context
    ctx.ensure_object(dict)
    ctx.obj['node_count'] = node_count
    ctx.obj['duration'] = duration
    ctx.obj['output_dir'] = output_dir
    ctx.obj['voltage_gain'] = IDEAL_VOLTAGE_GAIN
    ctx.obj['current_gain'] = IDEAL_CURRENT_GAIN

    if no_git:
        repo = None
        commit_hash = None
    else:
        try:
            repo, commit_hash, repo_root = get_git_info()
        except Exception as e:
            raise RuntimeError('Could not determine git info. Use `--no-git` to disable git metadata (will limit reproducability)') from e

    metadata = generate_meta(ctx=ctx, eenv_name=name, git_repository=repo, git_commit_hash=commit_hash, git_repository_root=repo_root)
    output_dir.mkdir()
    with open(output_dir / 'eenv.yaml', 'w') as meta_file:
        yaml.dump(metadata, meta_file, default_flow_style=False, sort_keys=False)

# Add the generator subcommands
for gen in GENERATORS:
    cli.add_command(gen)

def get_git_info():
    assert shutil.which('git') is not None, 'Git binary not executable'

    script_dir = Path(__file__).parent

    url = subprocess.run(args=['git', 'ls-remote', '--get-url'],
                         cwd=script_dir,
                         check=True,
                         capture_output=True,
                         encoding='utf-8').stdout.strip()
    if url.startswith('git@'):
        url = re.sub(r'git@(.+):(.+)\.git', r'https://\1/\2.git', url)
    elif not url.startswith('https://'):
        raise RuntimeError('Remote is neither ssh nor https')

    tree_dirty = len(subprocess.run(args=['git', 'diff-index', '--name-only', 'HEAD'],
                                    cwd=script_dir,
                                    check=True,
                                    capture_output=True,
                                    encoding='utf-8').stdout.strip()) > 0

    assert not tree_dirty, 'Git tree is dirty. Result would not be reproducable.'

    commit_hash = subprocess.run(args=['git', 'rev-parse', 'HEAD'], 
                                 cwd=script_dir,
                                 check=True,
                                 capture_output=True,
                                 encoding='utf-8').stdout.strip()

    root = subprocess.run(args=['git', 'rev-parse', '--show-toplevel'],
                                 cwd=script_dir,
                                 check=True,
                                 capture_output=True,
                                 encoding='utf-8').stdout.strip()

    return url, commit_hash, root

def generate_meta(ctx, eenv_name, git_repository, git_commit_hash, git_repository_root):
    '''
    Generates energy environment metadata based on the click context.
    '''
    generator_name = ctx.invoked_subcommand
    if git_repository_root is None:
        script_path = Path(__file__).name
    else:
        script_path = str(Path(__file__).relative_to(git_repository_root))

    # TODO specify metadata structure and possibly create a python interface for it
    metadata = {
        'datatype': 'EnergyEnvironment',
        'parameters': {
            'name': eenv_name,
            'description': GENERATOR_INFO[generator_name]['description'],
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'owner': 'Networked Embedded Systems Lab',
            'group': 'TU Darmstadt',
            'data_type': GENERATOR_INFO[generator_name]['data_type'],
            'nodes': ctx.obj['node_count'],
            'duration': ctx.obj['duration'],
            'environment': {
                'type': 'artificial',
                'generator': {
                    'repository': git_repository,
                    'commit_hash': git_commit_hash,
                    'script': script_path,
                    'parameters': ' '.join(sys.argv[1:])
                }, 
            }
        }
    }
    return metadata


if __name__ == '__main__':
    cli()
