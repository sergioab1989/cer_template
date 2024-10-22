#!/usr/bin/env python3

"""
Python script to create a PDF of the Red Hat training course files in the CER canned-content
"""

# This script will create a temporary top-level asciidoc file and add includes
# for all training documents and then use generage-pdf to create a pdf file
# will all of the training docs.
#
# The generated pdf will be named cer-training-test.pdf
#
# This script is most useful when testing changes to the refresh-training.py script

import os
import tempfile
import subprocess

tmp_file = tempfile.NamedTemporaryFile(
    "w+t", dir=os.curdir, delete=False, suffix=".adoc"
)
tmp_filename = tmp_file.name

try:
    print("Creating temporary adoc file...")

    print(
        ":lang: en_US\n"
        "include::vars/render-vars.adoc[]\n"
        "include::locale/attributes.adoc[]\n\n"
        "= Training Doc Testing: PDF containing all training files in Base CER directories\n\n"
        "<<<\n"
        "toc::[]\n\n"
        "<<<",
        file=tmp_file,
    )

    for lang in ["en_US", "es_US", "pt_BR", "de_DE", "fr_FR"]:
        print("== Training for: " + lang + "\n", file=tmp_file)

        TRAINING_DIR = "canned-content/" + lang + "/Base/training"

        for root, dirs, files in os.walk(TRAINING_DIR):
            for file in sorted(files):
                if file.endswith(".adoc"):
                    print(
                        "<<<\n"
                        "include::" + TRAINING_DIR + "/" + file + "[leveloffset=+2]\n",
                        file=tmp_file,
                    )

    tmp_file.close()

    print("Running generate-pdf with temporary adoc file...")
    result = subprocess.run(
        ["./generate-pdf", "-f", os.path.basename(tmp_filename), "-o", "training-test"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    print(result.stdout)

finally:
    os.remove(tmp_filename)
