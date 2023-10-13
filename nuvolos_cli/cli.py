import cmd
from .context import NuvolosContext
from .config import init_cli_config, info
from .api_client import list_orgs
from .utils import print_model_tabulated, print_models_tabulated


class NuvolosCli(cmd.Cmd):
    context = NuvolosContext()
    intro = r"""
 _   _                  _              ____ _     ___ 
| \ | |_   ___   _____ | | ___  ___   / ___| |   |_ _|
|  \| | | | \ \ / / _ \| |/ _ \/ __| | |   | |    | | 
| |\  | |_| |\ V / (_) | | (_) \__ \ | |___| |___ | | 
|_| \_|\__,_| \_/ \___/|_|\___/|___/  \____|_____|___|
    
Welcome to the Nuvolos CLI. Type help or ? to list commands.
"""
    prompt = "(nuvolos-cli) "

    def do_info(self):
        "Print information about the Nuvolos CLI"
        info()

    def do_config(self, api_key):
        init_cli_config(
            api_key=api_key,
        )

    def do_orgs(self, arg):
        "List the Nuvolos organizations"
        orgs = list_orgs()
        print_models_tabulated(orgs)

    def do_orgs_use(self, slug):
        "Set the current org in the NuvolosContext to the Org with slug of `slug`"
        self.context.set_current_org(slug)
        print(f"Current org set to {slug}")
