#!/bin/bash
# Script to parse README.adoc (or another file with the correct construct)
# The script will scan for the following in the file:
# ^//#? Statement #//
# contents 
# ^//## ##//
# It will present all optional and recommended sections, and ask if the need to be included. 
# It produces a new README.adoc and 

description_selector() {
   cat <<@SelectorDoc
There are 4 types available    
  #M = mandatory
  #R = recommended
  #O = optional
  #H = Header section

Mandatory will be included. 
Recommended sections are .. recommended to include but can be left out.
Optional means these are optional and can be dropped.
Header means this is a section providing a header for the next bit.

Be aware that when selecting here, they are removed from the README.adoc file.
No reference will be available. If they are kept in, the comments you see are 
also included in the file, providing you information on the section.

@SelectorDoc
}

# Function to display the available options
display_options() {
    description_selector
    awk '/^\/\/#/ {print NR": "$0}' "$filetoclean" |grep -v "//## ##//"
}

read_and_display_content() {
    local includefilename="$1"
    local counter=0

    while IFS= read -r displayline; do
        if [[ $displayline == "////"* ]]; then
            ((counter++))
            [[ $counter -eq 2 ]] && return 
        else 
           echo $displayline
        fi 
    done < "${includefilename}"
}

get_details() {
    # The content is in the files, and could be read like this, but the file is unknown at
    # this point, as all that is provided to the prompt_inclusion is the section_count, the type and the line. 
    local section_number="$1"
    local file="${filetoclean}"

    local current_section=0
    local found_section=false
    local include_filename=""

    while IFS= read -r detailline; do
        if [[ $detailline =~ ^\/\/#(M|R|O|H) ]]; then
            ((current_section++))
            if [ "$current_section" -eq "$section_number" ]; then
                # At the section
                found_section=true
            fi
        elif [ "$found_section" = true ] && [[ $detailline == "include::"* ]]; then
            # Found the first line that starts with "include::" after the section_number
            include_filename=$(echo ${detailline#include:: } | sed -e 's|include::||' -e 's|\[.*\]||' )
            # now we know the filename, next we need to read the file
            echo ${include_filename}:  
            read_and_display_content ${include_filename}
            return
        fi
    done < "$file"
}

# Function to prompt the user for inclusion
prompt_inclusion() {
    local section_type=$1
    shift
    local sect_count=$1
    shift
    local theline=$*
    echo -e "\n*****************************************************"
    if [[ ${section_type} == "M" || ${section_type} == "H" ]]; then
        echo -e "\n${sect_count}: Skipping selection as section is required..."
        return 0  # Include mandatory and headers sections without prompting
     fi


    while true; do
        printf "\n${sect_count}: This section is "
        echo "${theline}" | sed -e 's|//#R |recommended:\n|' -e 's|//#O |optional:\n|' -e 's|##//||'
        read -p "Include this section? [Y(es)/N(o)/D(etails)]: " choice </dev/tty
        case $choice in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            [Dd]* ) get_details ${sect_count} ;;
            * ) echo "Invalid input. Please enter Y or N.";;
        esac
    done
}

# Function to parse and save the selected sections
parse_sections() {
    local section_count=0
    local include_count=0
    local include_file="included_sections.txt"

    # Initialize the include file
    echo "" > "${include_file}"

    while read -r line; do
        if [[ $line =~ ^\/\/#(M|R|O|H) ]]; then
            section_count=$((section_count + 1))

            section_type="${BASH_REMATCH[1]}"
            if prompt_inclusion "${section_type}" "${section_count}" "${line}"; then
                include_count=$((include_count + 1))
                echo "${line%%//## ##//}" >> "${include_file}"

                # Read and save lines until the ending delimiter
                while read -r inner_line; do
                    echo "${inner_line}" >> "${include_file}"
                    if [[ ${inner_line} =~ ^\/\/##\ ##\/\/$ ]]; then
                        # add a whiteline between each section
                        echo "" >> ${include_file}
                        break
                    fi
                done
            fi
        fi
    done < "${filetoclean}"

    echo "Total sections found: $section_count"
    echo "Included sections: $include_count"
    
    # Only save an original, if it does not exist yet. 
    if [[ ! -f "${filetoclean}.original" ]] ; then 
        savefile="${filetoclean}.original"
    else
        mydate=$(date +%Y%m%d-%H%M%S)
        savefile="${filetoclean}.${mydate}"
    fi
    # Move the new file onto the original
    mv ${filetoclean} ${savefile}
    echo "Saved ${filetoclean} as ${savefile} "
    mv ${include_file} "${filetoclean}"
}

if [ $1 ] ; then 
  filetoclean=$1
else
  # Read the file path from the user
  read -p "Enter the path to the file: " filetoclean
fi

# Display available options
# display_options

# Parse and save the selected sections
cat <<@introduction


-----------------
Going read the file ** ${filetoclean} ** and provide some the information around the 
CER contents to provide a way to select which contents to keep.

Parsing contents... 
@introduction

parse_sections
