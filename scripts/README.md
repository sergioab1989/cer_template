# Scripts

This folder contains added scripts, added by anyone, which can help you making CER more effective.

Each script will have a specific function, so adding a new script would require you to describe in the script what it does, or provide a link to more information on the script.

## coalesce-asciidoc

Will coalesce the CER you've made into one file, effectively removing the chapter structure. It may be useful in some situations where Asciidoctor is not doing what you expect it to do.

## refresh-training.py

The python refresh-training.py script will pull courses from <https://www.redhat.com/en/services/training-and-certification> and update the associated Asciidocs in Base/training.

## refresh-training

Runs the refresh-training.py script in a container using either Podman or Docker.

### training-test-pdf.py

The training-test-pdf.py will generate a pdf with all the updated training files, to ensure the generated Asciidocs are correctly processed in the CER.

## generate-healthcheck.py

This script is used to generate healthcheck asciidoc files from a collection of items for OCP4.

They are complex enough that they have their own README-HEALTHCHECK.md, which is found with the canned-content they belong to, canned-content/en_US/OCP-4x-healthcheck/.

## clean-cer-contents.sh

This script supports the post init selection of contents.

It has its own [README](README-clean-cer-contents.md) file.\

