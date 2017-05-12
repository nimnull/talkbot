import json

import click
import trafaret as t

from talkbot.main import init

@click.group()
def main():
    pass


@main.command()
@click.option('--config', '-c', default="config.json", type=click.File(encoding='utf-8'))
def run(config):
    try:
        config_struct = json.load(config)
        init(config_struct)
    except json.decoder.JSONDecodeError as ex:
        click.echo("Failed to parse %s. %s" % (config.name, ex), err=True)
    except t.DataError as ex:
        for item in ex.as_dict().items():
            click.echo("Wrong attribute '%s' — '%s'" % item)
