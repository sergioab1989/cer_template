#!/usr/bin/env python3

import sys, yaml, click, csv, re
from os import path, listdir
from cerberus import Validator 
if (sys.version_info.minor < 8,):
    from typing_extensions import Final
    from typing import Tuple
else:
    from typing import Final, Tuple

class termcolors:
    header = '\033[95m'
    info = '\033[0;94m'
    ok_cyan = '\033[96m'
    ok_green = '\033[92m'
    warning = '\033[93m'
    error = '\033[91m'
    reset = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'

def __generate_asciidoc(items: dict, config: dict) -> str:
    "Generate acsciidoc from items"

    close_table: Final = "|===\n\n"

    # Write key table
    output = """= Key

[cols="1,3", options=header]
|===
|Value
|Description
"""
    uniqueStatues: set = set(())

    for status in config['statuses'].values():
        #Ensure that status with same text but different case are not added to the key table
        if status['text'].lower() not in uniqueStatues:
            uniqueStatues.add(status['text'].lower())
            output += f"""
|
{{set:cellbgcolor:{status['color']}}}
{status['text']}
|
{{set:cellbgcolor!}}
{status['description']}
"""
    output += close_table

    # Write summary table
    output += "= Summary\n\n"
    output += __generate_table_header()

    print(f"\n{termcolors.info}Processing Summary Table{termcolors.reset}")

    for category in config['categories'].keys():
        if category not in items:
            continue
        for item in items[category]:
            #print(f"""Processing Summary Table for '{item['filename']}'""")
            file = item['filename'].split('/')[-1]            
            print(f"{termcolors.ok_green}+{termcolors.reset} {file}")
            output += __generate_summary_row(item, config)

    output += close_table

    # Write detail sections
    for category in config['categories'].keys():
        if category not in items:
            continue

        output += f"""<<<

# {config['categories'][category]['text']}

"""
        output += """
// Reset bgcolor for future tables
[grid=none,frame=none]
|===
|{set:cellbgcolor!}
|===
"""
        output += __generate_table_header()

        print(f"\n{termcolors.info}Processing Category Section Table:{termcolors.reset} {category}")

        for item in items[category]:
            #print(f"""Processing Category Section Table for '{item['filename']}'""")
            file = item['filename'].split('/')[-1]            
            print(f"{termcolors.ok_green}+{termcolors.reset} {file}")
            output += __generate_summary_row(item, config)

        output += close_table

        # Page break between table and descriptions looks nice
        output += "<<<\n\n"

        print(f"\n{termcolors.info}Writing Detail Section:{termcolors.reset} {category}")

        # Generate detailed sections
        for item in items[category]:
            #print(f"""Writing Detail Section for '{item['filename']}'""")
            file = item['filename'].split('/')[-1]            
            print(f"{termcolors.ok_green}+{termcolors.reset} {file}")
            output += __generate_detail(item, config)

    # Write final invisible table
    # This resets the bgcolor for future tables
    output += """
// Reset bgcolor for future tables
[grid=none,frame=none]
|===
|{set:cellbgcolor!}
|===
"""

    return output

def __generate_table_header() -> str:
    "Generate a standard asciidoc table header for item table"

    return """
[cols="1,2,2,3", options=header]
|===
|*Category*
|*Item Evaluated*
|*Observed Result*
|*Recommendation*


"""


def __will_item_generate_detail(item: dict, config: dict) -> bool:
    "Determine if an item file will cause a detail section to be generated."

    # Right now there is no difference between v0 and v1
    # if item['version'] == 'v0':
    #     return __will_item_generate_detail_v0(item, config)
    # if item['version'] == 'v1':
    #     return __will_item_generate_detail_v1(item, config)    


    # Only create section if not recommendation is not a skippable one
    # (defined in config) -OR- if additional_comments_text is defined.
    if item['version'] == 'v2':
        if (item['customer_environment_findings']['additional_comments']['impact_risk_additional_text'] != "" or
            item['customer_environment_findings']['additional_comments']['remediation_additional_text'] != "" or
            item['customer_environment_findings']['additional_comments']['additional_comments_text'] != "" or
            item['customer_environment_findings']['status'] not in config['skip_statuses']):
            return True
        else:
            return False
    else:
        if (item['results']['additional_comments_text'] != "" or
            item['results']['recommendation'] not in config['skip_statuses']):
            return True
        else:
            return False



def __helper_get_scenario_description_short_text(item: dict, config: dict) -> str:
    "Helper function to get scenario description short text"
    
    if item['customer_environment_findings']['outcome_overrides']["scenario_description_short_text"] != "":
        return item['customer_environment_findings']['outcome_overrides']["scenario_description_short_text"]
    for outcome in item['check_definition']['common_outcomes']:
        if item['customer_environment_findings']['common_outcome_key'] == outcome['key']:
            return outcome['scenario_description_short_text']    
    return ''

def __generate_detail(item: dict, config: dict) -> str:
    "Generate an AsciiDoc detail section"

    if item['version'] == 'v0':
        return __generate_detail_v0(item, config)
    if item['version'] == 'v1':
        return __generate_detail_v1(item, config)
    if item['version'] == 'v2':
        return __generate_detail_v2(item, config)

def __generate_detail_v0 (item: dict, config: dict) -> str:
    "Generate an AsciiDoc detail section for a v0 item file"

    output: str = ""
    results: dict = item['results']
    metadata: dict = item['metadata']

    if __will_item_generate_detail(item, config):

        # Anchor
        anchor_id = __get_itemid(item['filename'])
        output += "[#item-" + anchor_id + "]\n"

        # Write descriptions
        output += f"""## {item['metadata']['item_evaluated']}

[cols=\"^\"]
|===
|
{{set:cellbgcolor:{config['statuses'][results['recommendation']]['color']}}}
{config['statuses'][results['recommendation']]['text']}
|===

*Observed Result*

{item['results']['result_text']}

"""

        if ('acceptance_criteria' in metadata and
            results['recommendation'] in metadata['acceptance_criteria']):
            output += """*Matching Status(es)*

"""

            for matching_status in metadata['acceptance_criteria'][results['recommendation']]:
                output += f"* {matching_status}\n"
            output += "\n"

        if results['recommendation'] not in config['skip_statuses']:
            if results['impact_risk_text'] != "":
                output += f"""*Impact and Risk*

{results['impact_risk_text']}

"""

            if results['remediation_text'] != "":
                output += f"""*Remediation Advice*

{results['remediation_text']}

"""

        if results['additional_comments_text'] != "":
            output += f"""*Additional Comments*

{results['additional_comments_text']}

"""

        if len(metadata['references']) > 0:
            output += """*Reference Link(s)*

"""
            for ref in metadata['references']:
                output += f"* {ref['url']}[{ref['title']}]\n"

            output += "\n"

    return output

def __generate_detail_v1 (item: dict, config: dict) -> str:
    "Generate an AsciiDoc detail section for a v0 item file"
    
    output: str = ""
    results: dict = item['results']
    metadata: dict = item['metadata']

    if __will_item_generate_detail(item, config):

        # Anchor
        anchor_id = __get_itemid(item['filename'])
        output += "[#item-" + anchor_id + "]\n"

        # Write descriptions
        output += f"""## {item['metadata']['item_evaluated']}

[cols=\"^\"]
|===
|
{{set:cellbgcolor:{config['statuses'][results['recommendation']]['color']}}}
{config['statuses'][results['recommendation']]['text']}
|===

*Observed Result*
"""
        output += f"""

*Summary:*  {item['results']['result_short_text']}

"""


        if 'result_long_text' in results:
            output += f"""

{item['results']['result_long_text']}

"""


        # Only write impact and remedation if not in a skippable status
        if results['recommendation'] not in config['skip_statuses']:
            ac_verbiage = {}

            if ('acceptance_criteria' in metadata and
                results['recommendation'] in metadata['acceptance_criteria']):

                
                for status in metadata['acceptance_criteria'][results['recommendation']]:
                    if status['id'] == results['acceptance_criteria_id']:
                        ac_verbiage = status

            if 'condition_description' in ac_verbiage:
                output += f"""*Matching Condition*

{ac_verbiage['condition_description']}

"""
            output += f"""*Impact and Risk*
"""
            if 'impact_risk_text' in ac_verbiage:
                output += f"""
{ac_verbiage['impact_risk_text']}

"""
                if results['impact_risk_additional_text'] != "":
                    output += f"""*Additional Consultant Comments Impact and Risk*
"""
            output += f"""
{results['impact_risk_additional_text']}

"""

            output += f"""*Remediation Advice*
"""
            if 'remediation_text' in ac_verbiage:
                output += f"""
{ac_verbiage['remediation_text']}

"""
                if results['remediation_additional_text'] != "":
                    output += f"""*Additional Consultant Comments for Remediation*
"""
            output += f"""
{results['remediation_additional_text']}

"""


        if results['additional_comments_text'] != "":
            output += f"""*Additional Comments*

{results['additional_comments_text']}

"""

        if len(metadata['references']) > 0:
            output += """*Reference Link(s)*

"""
            for ref in metadata['references']:
                output += f"* {ref['url']}[{ref['title']}]\n"

            output += "\n"


    return output

def __generate_detail_v2 (item: dict, config: dict) -> str:
    "Generate an AsciiDoc detail section for a v2 item file"

    output: str = ""
    results: dict = item['customer_environment_findings']
    metadata: dict = item['check_definition']

    if __will_item_generate_detail(item, config):
        
        # Anchor
        anchor_id = __get_itemid(item['filename'])
        output += "[#item-" + anchor_id + "]\n"

        output += f"""## {item['check_definition']['description']}
[cols=\"^\"]
|===
|
{{set:cellbgcolor:{config['statuses'][results['status']]['color']}}}
{config['statuses'][results['status']]['text']}
|===

"""
        if results['status'] not in config['skip_statuses']:
            ac_verbiage = {}

            for outcome in metadata['common_outcomes']:
                if results['common_outcome_key'] == outcome['key']:
                    ac_verbiage = outcome

            if ('outcome_overrides' in results):
                overrides = results['outcome_overrides']

                if ('scenario_description_short_text' in overrides and
                    overrides['scenario_description_short_text'] != ""):
                    
                    ac_verbiage['scenario_description_short_text'] = overrides['scenario_description_short_text']
                if ('description_long_text' in overrides and
                    overrides['description_long_text'] != ""):
                    
                    ac_verbiage['description_long_text'] = overrides['description_long_text']

                if ('impact_and_risk_text' in overrides and
                    overrides['impact_and_risk_text'] != ""):
                    
                    ac_verbiage['impact_and_risk_text'] = overrides['impact_and_risk_text']

                if ('remediation_text' in overrides and
                    overrides['remediation_text'] != ""):
                    
                    ac_verbiage['remediation_text'] = overrides['remediation_text']

            output += __generate_outcomes_ascii_v2(ac_verbiage)
        
        output += __generate_additional_comments_ascii_v2(results)

        if len(metadata['references']) > 0:
            output += """*Reference Link(s)*

"""
            for ref in metadata['references']:
                output += f"""* {ref['url']}[{ref['title']}]\n"""
            output += "\n"



    return(output)


def __generate_additional_comments_ascii_v2(results: dict) -> str:
    output: str = ""

    if (results['additional_comments']['additional_comments_text'] != ""):
        output += f"""*Additional Comments*
"""
        output += f"""

{results['additional_comments']['additional_comments_text']}

"""
    if (results['additional_comments']['impact_risk_additional_text'] != ""):
        output += f"""*Additional Consultant Comments Impact and Risk*
"""
        output += f"""
{results['additional_comments']['impact_risk_additional_text']}

"""
    if (results['additional_comments']['remediation_additional_text'] != ""):
        output += f"""*Additional Consultant Comments for Remediation*
"""
        output += f"""
{results['additional_comments']['remediation_additional_text']}

"""
    return output

def __generate_outcomes_ascii_v2(ac_verbiage: dict) -> str:
    "Generate an AsciiDoc detail section for a v2 item file"
    output: str = ""

    if 'scenario_description_short_text' in ac_verbiage:
        output += f"""*Findings*

"""
        output += f"""
{ac_verbiage['scenario_description_short_text']}

"""
    
    if ('description_long_text' in ac_verbiage and
        ac_verbiage['description_long_text'] != ""):
        output += f"""*Description*
"""
        output += f"""
{ac_verbiage['description_long_text']}

"""
    if ('impact_and_risk_text' in ac_verbiage and
        ac_verbiage['impact_and_risk_text'] != ""):
        output += f"""*Impact and Risk*

"""
        output += f"""

{ac_verbiage['impact_and_risk_text']}

"""
    if ('remediation_text' in ac_verbiage and
        ac_verbiage['remediation_text'] != ""):
        output += f"""*Remediation Advice*
"""
        output += f"""
{ac_verbiage['remediation_text']}

"""
    return output

def __generate_summary_row(item: dict, config: dict) -> str:
    "Generate an AsciiDoc Summary Table Row"

    if item['version'] == 'v0':
        return __generate_summary_row_v0(item, config)
    if item['version'] == 'v1':
        return __generate_summary_row_v1(item, config)
    if item['version'] == 'v2':
        return __generate_summary_row_v2(item, config)


def __generate_summary_row_v0(item: dict, config: dict) -> str:
    "Generate an AsciiDoc Summary Table Row for item file v0"

    output = f"""
// ------------------------ITEM START
// ----ITEM SOURCE:  {item['filename']}

// Category
|
{{set:cellbgcolor!}}
{config['categories'][item['metadata']['category_key']]['short_text']}

// Item Evaluated
a|
"""
    if __will_item_generate_detail(item, config):
        anchor_id = __get_itemid(item['filename'])
        output += f"""<<item-{anchor_id},{item['check_definition']['description']}>>"""
    else:
        output += f"""{item['metadata']['item_evaluated']}"""

    output += f"""

// Result
| 
{item['results']['result_text']}

// Recommendation
| 
{{set:cellbgcolor:{config['statuses'][item['results']['recommendation']]['color']}}}
{config['statuses'][item['results']['recommendation']]['text']}

// ------------------------ITEM END
"""

    return output

def __generate_summary_row_v1(item: dict, config: dict) -> str:
    "Generate an AsciiDoc Summary Table Row for item file v1"

    output = f"""
// ------------------------ITEM START
// ----ITEM SOURCE:  {item['filename']}

// Category
|
{{set:cellbgcolor!}}
{config['categories'][item['metadata']['category_key']]['short_text']}

// Item Evaluated
a|
"""
    if __will_item_generate_detail(item, config):
        anchor_id = __get_itemid(item['filename'])
        output += f"""<<item-{anchor_id},{item['metadata']['item_evaluated']}>>"""
    else:
        output += f"""{item['metadata']['item_evaluated']}"""
    
    output += f"""

// Result
| 
{item['results']['result_short_text']}

// Recommendation
| 
{{set:cellbgcolor:{config['statuses'][item['results']['recommendation']]['color']}}}
{config['statuses'][item['results']['recommendation']]['text']}

// ------------------------ITEM END
"""

    return output

def __generate_summary_row_v2(item: dict, config: dict) -> str:
    "Generate an AsciiDoc Summary Table Row for item file v2"
    short_text = __helper_get_scenario_description_short_text(item, config)
    output = f"""
// ------------------------ITEM START
// ----ITEM SOURCE:  {item['filename']}

// Category
|
{{set:cellbgcolor!}}
{config['categories'][item['check_definition']['category_key']]['short_text']}

// Item Evaluated
a|
"""
    if __will_item_generate_detail(item, config):
        anchor_id = __get_itemid(item['filename'])
        output += f"""<<item-{anchor_id},{item['check_definition']['description']}>>"""
    else:
         output += f"""{item['check_definition']['description']}"""
    
    output += f"""

// Result
| 
{short_text}

// Recommendation
| 
{{set:cellbgcolor:{config['statuses'][item['customer_environment_findings']['status']]['color']}}}
{config['statuses'][item['customer_environment_findings']['status']]['text']}
// ------------------------ITEM END
"""

    return output

def __is_item_valid(item: dict, config: dict):
    "Validate a loaded item file this assumes it passes regular YAML validation"
    message: str = ""
    if 'version' in item:
        if item['version'] == 'v0' or item['version'] == 'v1':
            try:
                if item["results"]["recommendation"] not in config["statuses"].keys():
                    message = f"""Invalid recommendation value: '{item['results']['recommendation']}'"""

                if item["metadata"]["category_key"] not in config["categories"].keys():
                    message = f"""Invalid category value:  '{item['metadata']['category_key']}'"""

            except KeyError as e:
                message = f"""Missing key: {e}"""

            if message != "":
                return False, message

        elif item['version'] == 'v2':
            matching_dict: dict = None
            try:
                if item["customer_environment_findings"]["status"] not in config["statuses"].keys():
                    message = f"""Invalid recommendation value: '{item['customer_environment_findings']['status']}'"""

                if item["check_definition"]["category_key"] not in config["categories"].keys():
                    message = f"""Invalid category value:  '{item['check_definition']['category_key']}'"""

            except KeyError as e:
                message = f"""Missing key: {e}"""

            if message != "":
                return False, message
            
            if ('outcome_overrides' not in item["customer_environment_findings"]):
                for outcome in item["check_definition"]["common_outcomes"]:
                    if item["customer_environment_findings"]["common_outcome_key"] == outcome["key"]:
                        matching_dict = outcome
                if matching_dict is None:
                    message = f"""common_outcome_key does not exist:  '{item['customer_environment_findings']['common_outcome_key']}'"""
            if message != "":
                return False, message
                            
            
        if item['version'] == 'v1':
            if ('acceptance_criteria_id' in item['results'] and 
                item['results']['acceptance_criteria_id'] != ""):
                
                matching_dict: dict = None
                matching_id: str = item['results']['acceptance_criteria_id']

                for status in item['metadata']['acceptance_criteria'][item['results']['recommendation']]:
                    if status['id'] == matching_id:
                        matching_dict = status

                if matching_dict is None:
                    message = f"""acceptance_criteria_id does not exist:  '{item['results']['acceptance_criteria_id']}'"""
            if message != "":
                return False, message


        if message != "":
            return False, message
        else:
            return True, "" 
    else:
        return False, "Unknown item version"

def __load_config(input_dir: str) -> dict:
    "Load config and categories settings"

    config_file: str = path.join(input_dir, "config.yaml")
    categories_file: str = path.join(input_dir, "categories.yaml")

    # Load config
    try:
        with open(config_file) as f:
            config: dict = yaml.safe_load(f)
    except FileNotFoundError:
        # Set default config
        config: dict = {
            "statuses": {
                "changes_required": {
                    "color": "#FF0000",
                    "text": "Changes Required",
                    "description": "Indicates Changes Required for system stability, subscription compliance, or other reason.", # pylint: disable=line-too-long
                },
                "changes_recommended": {
                    "color": "#FEFE20",
                    "text": "Changes Recommended",
                    "description": "Indicates Changes Recommended to align with recommended practices, but not urgently required.", # pylint: disable=line-too-long
                },
                "not_applicable": {
                    "color": "#A6B9BF",
                    "text": "N/A",
                    "description": "No advice given on line item.  For line items which are data-only to provide context.", # pylint: disable=line-too-long
                },
                "advisory": {
                    "color": "#80E5FF",
                    "text": "Advisory",
                    "description": "No change required or recommended, but additional information provided.", # pylint: disable=line-too-long
                },
                "no_change": {
                    "color": "#00FF00",
                    "text": "No Change",
                    "description": "No change required.  In alignment with recommended practices.",
                },
                "tbe": {
                    "color": "#FFFFFF",
                    "text": "To Be Evaluated",
                    "description": "Not yet evaluated.  Will appear only in draft copies.",
                },
                "fail": {
                    "color": "#FF0000",
                    "text": "Changes Required",
                    "description": "Indicates Changes Required for system stability, subscription compliance, or other reason.", # pylint: disable=line-too-long
                },
                "pass": {
                    "color": "#00FF00",
                    "text": "No Change",
                    "description": "No change required.  In alignment with recommended practices.",
                },
                "inconclusive": {
                    "color": "FFFFFF",
                    "text": "Inconclusive",
                    "description": "Unable to make a recommendation.",
                },
                "na": {
                    "color": "#A6B9BF",
                    "text": "N/A",
                    "description": "No advice given on line item.  For line items which are data-only to provide context.", # pylint: disable=line-too-long
                },
            },
            "skip_statuses": ["not_applicable", "tbe", "no_change", "inconclusive", "na"]
        }

    # Load categories
    try:
        with open(categories_file) as f:
            config["categories"] = yaml.safe_load(f)["categories"]
    except FileNotFoundError:
        print(f"No categories file found at {categories_file}", file=sys.stderr)
        sys.exit(1)

    return config

def __load_items(input_dir: str, config: dict) -> dict:
    "Load healthcheck items"

    items: dict = {}
    global load_errors
    load_errors = 0
    item_files: list[str] = [path.join(input_dir, f)
                  for f in sorted(listdir(input_dir))
                  if f.endswith('.item') or f.endswith('.item.yaml')]
    global failed_item_files
    failed_item_files = []


    print(f"\n{termcolors.info}Loading Item Files:{termcolors.reset} {input_dir}*")
    for item_file in item_files:
        file = item_file.split('/')[-1]
        print(f"{termcolors.ok_green}+{termcolors.reset} {file}")
        #print(f"""Loading '{item_file}'""")
        try: 
            with open(item_file) as f:
                item: dict = yaml.safe_load(f)

                is_valid, message = __is_item_valid(item, config)
                is_valid_schema, schema_message = __validate_yaml(item_file)

                if is_valid is not True or is_valid_schema is not True:
                    load_errors += 1
                    if is_valid is not True:
                        print(f"""{termcolors.error}-{termcolors.reset} {file}""")
                        failed_item_files.append(f"""{termcolors.error}-{termcolors.reset} File Validation Error:
                        {message} in file '{item_file}'""")
                    if is_valid_schema is not True:
                        print(f"""{termcolors.error}-{termcolors.reset} {file}""", file=sys.stderr)
                        failed_item_files.append(f"""{termcolors.error}-{termcolors.reset} File Validation Error:
                        {schema_message} in file '{item_file}'""")
                    continue

                item["filename"] = item_file

        
        except Exception as e:
            load_errors += 1
            print(f"{termcolors.error}-{termcolors.reset} {file}")          
            #print(f"""YAML Parse Error:
            print(f"""{termcolors.error}\nYAML Parse Error:
            {e} in file '{item}'\n{termcolors.reset}""", file=sys.stderr)
            continue
        if (item['version'] == 'v2'):
            items.setdefault(item["check_definition"]["category_key"], []).append(item)
        else:
            items.setdefault(item["metadata"]["category_key"], []).append(item)

    if load_errors > 0:
        print(f"\n{termcolors.error}There were {load_errors} loading errors:{termcolors.reset}", file=sys.stderr)
        for file in failed_item_files:
            print(f"  {file}")
        # sys.exit(1)


    return items

def __load_healthcheck(input_dir: str) -> Tuple[dict, dict]:
    "Load Healthcheck Items and Config"

    config: dict = __load_config(input_dir)
    items: dict = __load_items(input_dir, config)

    return items, config

# Gets an "ID" for an item, to be used in the ID attribute and cross-references
def __get_itemid(item_filename: str):
    match = re.search(r'(\d+.+)\.(item|item\.yaml)', item_filename)
    if match:
        return match.group(1)
    print("ERROR: could not get item ID for " + item_filename + "\n")


@click.group()
def cli():
    pass


# click.Path(exists=False, file_okay=True, dir_okay=True, writable=False, readable=True, resolve_path=False, allow_dash=False, path_type=None)

@cli.command()
@click.option('--input-dir', default="./content/healthcheck-items/", show_default=True, type=click.Path(exists=True, file_okay=False))
@click.option('--output-file', default="./content/healthcheck-body.adoc", show_default=True, type=click.Path(dir_okay=False))
def asciidoc(input_dir: str, output_file: str):
    "Generate Healthcheck AsciiDoc"

    click.echo(f"{termcolors.ok_green}Generating AsciiDoc {output_file}{termcolors.reset}")

    items, config = __load_healthcheck(input_dir)

    adoc: str = __generate_asciidoc(items, config)

    with open(output_file, "w") as f:
        f.write("// ---------------------------------------------------------------------\n")
        f.write("// WARNING: AUTOMATICALLY GENERATED FILE\n")
        f.write("// This file has been automatically generated by generate-healthcheck.py\n")
        f.write("// Manual changes discouraged; they may be overwritten\n")
        f.write("// ---------------------------------------------------------------------\n")
        f.write(adoc)

    item_count = 0
    click.echo(f"\nTotal Categories Processed: {str(len(items))}\n")
    for category in items.keys():
        item_count += (int(len(items[category])))
        # click.echo("   Category " + category + " processed " + str(len(items[category])) + " items.")
        click.echo(f"  {str(len(items[category]))} items: {category}")
    
    click.echo(f"\nTotal Items Processed: {item_count}")
    
    if (load_errors > 0 ):
        click.echo(f'\nThere were{termcolors.error} {str(load_errors)} {termcolors.reset}items skipped due to load errors.')
        
        for file in failed_item_files:
            click.echo(f"  {termcolors.error}{file}{termcolors.reset}")
        click.echo(f"\nPlease check above for details of load errors.")
        
    elif (load_errors == 0):
        click.echo(f'\nThere were{termcolors.ok_green} {str(load_errors)} {termcolors.reset}items skipped due to load errors.')
        

@cli.command()
@click.option('--input-dir', default="./content/healthcheck-items/", show_default=True, type=click.Path(exists=True, file_okay=False))
@click.option('--output-file', default="./content/healthcheck.csv", show_default=True, type=click.Path(dir_okay=False))
def exportcsv(input_dir: str, output_file: str):
    "Generate healthcheck csv"

    click.echo(f"Generating csv {output_file}")

    items, config = __load_healthcheck(input_dir)

    with open(output_file, "w", newline='') as csvfile:
        fieldnames = ["Category","Item Evaluated","Observed Result","Recommendation","Version","Source"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for category in config['categories'].keys():
            if category not in items:
                print(f"""The category: {category} is not in use""")
                continue
            for item in items[category]:
                if item['version'] == 'v0':
                    print(f"""Adding CSV row for '{item['filename']}""")
                    writer.writerow({'Category': config['categories'][item['metadata']['category_key']]['short_text'], 'Item Evaluated': item['metadata']['item_evaluated'], 'Observed Result': item['results']['result_text'], 'Recommendation': config['statuses'][item['results']['recommendation']]['text'], 'Version': item['version'], 'Source': item['filename']}) 
                elif item['version'] == 'v1':
                    print(f"""Adding CSV row for '{item['filename']}""")
                    writer.writerow({'Category': config['categories'][item['metadata']['category_key']]['short_text'], 'Item Evaluated': item['metadata']['item_evaluated'], 'Observed Result': item['results']['result_short_text'], 'Recommendation': config['statuses'][item['results']['recommendation']]['text'], 'Version': item['version'], 'Source': item['filename']}) 
                elif item["version"] == 'v2':
                    writer.writerow({'Category': config['categories'][item['check_definition']['category_key']]['short_text'], 'Item Evaluated': item['check_definition']['description'], 'Observed Result': item['customer_environment_findings']['status'], 'Recommendation': config['statuses'][item['customer_environment_findings']['status']]['text'], 'Version': item['version'], 'Source': item['filename']})

    click.echo("Completed. Please check above for errors.")


@cli.command()
@click.argument('dirname', type=click.Path(exists=True, file_okay=False))
def validate_dir(dirname: str):
    "Validate yaml of all item files in a directory"
    # use validate_item to validate a single item file
    # this is a wrapper to validate all item files in a directory

    item_files: list[str] = [path.join(dirname, f) for f in sorted(listdir(dirname)) if f.endswith('.item') or f.endswith('.item.yaml')]   
    print(f"\n{termcolors.info}Validating Item Files:{termcolors.reset} {dirname}*")

    invalid_items = []

    for item_file in item_files:         
        is_valid, message = __validate_yaml(item_file)
        if is_valid is not True:
            print(f"""{termcolors.error}-{termcolors.reset}: {item_file} {message} in file '{item_file}'""", file=sys.stderr)
            invalid_items.append({"item_file": item_file, "message": message})
        else:
            print(f"{termcolors.ok_green}+{termcolors.reset} {item_file}")

    if len(invalid_items) > 0:
        print(f"\n\n\nList of Errors:  ")
        for err in invalid_items:
            print(f"""{termcolors.error}-{termcolors.reset}:  {err['message']} in file '{err['item_file']}'""", file=sys.stderr)
        print(f""" {len(invalid_items)} errors encountered.""")
    else:
        print(f"No errors encountered.")

@cli.command()
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
def validate_item(filename: str):
    "Validate a single item file"

    print(f"{termcolors.info}Validating Item File:{termcolors.reset} {filename}")
    is_valid, message = __validate_yaml(filename)
    if is_valid is not True:
        print(f"""File Validation Error:
        {message} in file '{filename}'""", file=sys.stderr)
        return message
    else:
        print(f"{termcolors.ok_green}+{termcolors.reset} {filename}")
        return message


def __validate_yaml(filename: str) -> (bool, str):
    "Validate a yaml file"

    try:
        with open(filename) as f:
            item: dict = yaml.safe_load(f)
    except Exception:
        return (False, "File Load/YAML Parse Error.")

    if 'version' not in item.keys():
        return (False, "No version key.")
    
    # add "allowed": ['one','two']
    if item['version'] == 'v2':
        schema = {
            "version": {"type": "string", "required": True},
            "check_definition": {
                "type": "dict",
                "required": True,
                "schema": {
                    "category_key": {"type": "string", "required": True,},
                    "subcategory_key": {"type": "string", "required": True},
                    "severity_key": {"type": "string", "required": True},
                    "tag_keys": {"type": "list", "required": False},
                    "flags": {
                        "type": "dict",
                        "required": True,
                        "schema": {
                            "self_managed_only": {"type": "boolean", "required": False},
                        }
                    },
                    "description": {"type": "string", "required": True},
                    "common_outcomes": {
                        "type": "list", 
                        "required": True,
                        "schema": {
                            "type": "dict",
                            "schema": {
                               "key": {"type": "string", "required": True},
                               "scenario_description_short_text": {"type": "string", "required": True},
                               "description_long_text": {"type": "string", "required": False},
                               "impact_and_risk_text": {"type": "string", "required": False},
                               "remediation_text": {"type": "string", "required": False},
                            }
                        }
                    },
                    "references": {"type": "list", "required": True},
                    "check_procedures": {"type": "list", "required": False},
                }
            },
            "customer_environment_findings": {
                "type": "dict",
                "required": True,
                "schema": {
                    "status": {"type": "string", "required": True},
                    "common_outcome_key": {"type": "string", "required": True},
                    "outcome_overrides": {
                        "type": "dict", 
                        "required": False,
                        "schema": {
                            "scenario_description_short_text": {"type": "string", "required": False},
                            "description_long_text": {"type": "string", "required": False},
                            "impact_and_risk_text": {"type": "string", "required": False},
                            "remediation_text": {"type": "string", "required": False},
                        },
                    },
                    "additional_comments": {
                        "type": "dict",
                        "required": False,
                        "schema": {
                            "additional_comments_text": {"type": "string", "required": False},
                            "impact_risk_additional_text": {"type": "string", "required": False},
                            "remediation_additional_text": {"type": "string", "required": False},
                        }
                    },
                }
            },
        }
    else:
        return (False, "Not a v2 file")


    v = Validator()


    if not v.validate(item, schema):
        return (False, v.errors)
    else:
        return (True, "Validation OK")

@cli.command()
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
def zap(filename: str):
    'Reset customer environment findings to default values'
    
    with open(filename) as f:
        item: dict = yaml.safe_load(f)

    if item['version'] == 'v2':
        item['customer_environment_findings']['status'] = "tbe"
        item['customer_environment_findings']['common_outcome_key'] = ""
        item['customer_environment_findings']['outcome_overrides'] = {
            "scenario_description_short_text": "",
            "description_long_text": "",
            "impact_and_risk_text": "",
            "remediation_text": ""
        }
        item['customer_environment_findings']['additional_comments'] = {
            "additional_comments_text": "",
            "impact_risk_additional_text": "",
            "remediation_additional_text": ""
        }

    with open(filename, "w") as f:
        f.write(yaml.dump(item, default_flow_style=False, sort_keys=False))

    print(f"{termcolors.ok_green}+{termcolors.reset} {filename}")


    return True

@cli.command()
@click.option('--input-dir', default="./content/healthcheck-items/", show_default=True, type=click.Path(exists=True, file_okay=False))
@click.option('--output-file', default="./content/check-procedures.txt", show_default=True, type=click.Path(dir_okay=False))
def check_procedures(input_dir: str, output_file: str):
    "Create a list of all check procedures in a directory of healthcheck items"

    item_files: list[str] = [path.join(input_dir, f) for f in sorted(listdir(input_dir)) if f.endswith('.item') or f.endswith('.item.yaml')]
    output = f"""Check Procedures in {input_dir}:\n"""
    output += f"""_________________________________________________________"""


    for item_file in item_files:
        output += f"""\n{item_file}\n"""
        with open(item_file) as f:
            item: dict = yaml.safe_load(f)
            if item['version'] == 'v2':
                if 'check_procedures' in item['check_definition']:
                    for procedure in item['check_definition']['check_procedures']:
                        for key, value in procedure.items():
                            output += f"""\n{key}: {value}"""
                        output += f"""\n"""
        output += f"""_________________________________________________________"""
    with open(output_file, "w") as f:
        f.write(output)

    print(f"Check Procedures written to {output_file}")
    
if __name__ == "__main__":
    cli()
