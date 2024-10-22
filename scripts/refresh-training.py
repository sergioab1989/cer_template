#!/usr/bin/env python3

# pylint: disable=too-many-lines

"""
Python script to update the Red Hat training course files in the CER canned-content
"""

import json
import argparse
import traceback
import os
import sys
import tempfile
import errno
from datetime import datetime
import requests
from lxml import html
from lxml.etree import ParseError, ParserError

##############################
#
# Exception Classes
#
##############################


class NoContentFound(Exception):
    """Raised when course details cannot be found"""


class PageNotFound(Exception):
    """Raised when course page cannot be found"""


class ServiceUnavailable(Exception):
    """Raised when course page returns a service unavailable error"""


class EmptyPage(Exception):
    """Raised when course page has no content"""


class UnexpectedResponseCode(Exception):
    """Raised when HTTP request returns an unexpected status_code"""


class ReadTimeout(Exception):
    """Raised when HTTP request times out"""


class TooManyRedirects(Exception):
    """Raised when HTTP request is redirected too many times"""


class UnsupportedLanguage(Exception):
    """Raised when the language specified is not supported"""

    def __init__(self, lang, message="Language not supported"):
        self.lang = lang
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.lang} -> {self.message}"


class NoLanguage(Exception):
    """Raised when the language is not set"""

    def __init__(self, message="Language is not set"):
        self.message = message
        super().__init__(self.message)


class NoOutputDir(Exception):
    """Raised when the output directory is not set"""

    def __init__(self, message="Output directory not set"):
        self.message = message
        super().__init__(self.message)


class OutputDirNotWriteable(Exception):
    """Raised when the default output directory is not writeable"""

    def __init__(self, directory, message="Output directory is not writeable"):
        self.directory = directory
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.directory} -> {self.message}"


class OutputDirNotFound(Exception):
    """Raised when the default output directory is not found"""

    def __init__(
        self,
        directory,
        message=(
            "Output directory is not a directory or does not exist. "
            "Please run from CER root directory."
        ),
    ):
        self.directory = directory
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.directory} -> {self.message}"


##############################
#
# Traning Class
#
##############################


class CERTraining:
    """
    Updates CER asciidoc training files from public Red Hat course data
    """

    supported_languages = {
        "en": {
            "lang_name": "English",
            "cer_locale": "en_US",
            "overview_ids": ["Overview", " Overview", "overview"],
            "details_text": "For full details, or to enroll:",
            "comment_text": (
                "// This file is maintained by running "
                "scripts/refresh-training.py script\n\n"
            ),
        },
        "fr": {
            "lang_name": "Français",
            "cer_locale": "fr_FR",
            "overview_ids": ["présentation"],
            "details_text": "Pour plus de détails ou pour s'inscrire :",
            "comment_text": (
                "// This file is maintained by running "
                "scripts/refresh-training.py script\n\n"
            ),
        },
        "pt-br": {
            "lang_name": "Português",
            "cer_locale": "pt_BR",
            "overview_ids": ["Visão geral", "visão-geral", "Overview", "overview"],
            "details_text": "Para mais detalhes ou para se inscrever:",
            "comment_text": (
                "// Este arquivo é mantido executando "
                "scripts/refresh-training.py script\n\n"
            ),
        },
        "es": {
            "lang_name": "Español",
            "cer_locale": "es_US",
            "overview_ids": [
                "Descripción general",
                "Descripción General",
                "Descripción",
                "Resumen",
                "resumen",
                "Overview",
                "overview",
            ],
            "details_text": "Para más detalles, o para inscribirse:",
            "comment_text": (
                "// Este archivo se mantiene ejecutando "
                "scripts/refresh-training.py script\n\n"
            ),
        },
        "de": {
            "lang_name": "German",
            "cer_locale": "de_DE",
            "overview_ids": ["Überblick", "überblick", "Overview", "overview"],
            "details_text": "Ausführliche Informationen oder Anmeldung:",
            "comment_text": (
                "// Diese Datei wird durch Ausführen des "
                "Skripts scripts/refresh-training.py verwaltet\n\n"
            ),
        },
    }

    def __init__(self, **kwargs):
        self.tid = "1151"
        self.title_class = "rh-band-header-headline"
        self.c_id_class = "rh-band-header-title"
        self.image_class = "rhdc-media__image-link"

        self.verbosity = kwargs.get("verbosity", False)
        self.no_color = kwargs.get("no_color", False)
        self.quiet = kwargs.get("quiet", False)
        self.cleanup = kwargs.get("cleanup", False)
        self.debug = kwargs.get("debug", False)

        self.lang = kwargs.get("lang", "")
        self.output_dir = kwargs.get("output_dir", "")

        self.html_parser = html.HTMLParser(remove_comments=True)

    @property
    def output_dir(self):
        """Returns the directory path that the output files will be saved in"""
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value):
        """Defines the directory path to save the output files in.
        Setting the directory will fail if the directory is not writeable.
        If setting the directory to the default (e.g. passing in an empty string)
        the language must have already been set.
        """
        dir_path = ""

        if value:
            dir_path = os.path.abspath(value)
        else:
            if not self.lang:
                # Setting a default path requires the language to be set so
                # if it is not set then set the directory to an empty string
                # and return
                self._output_dir = ""
                return

            dir_path = os.path.abspath(
                "canned-content/" + self.cer_locale + "/Base/training"
            )

        # Test that the directory path exists and is writeable
        if not os.path.isdir(dir_path):
            raise OutputDirNotFound(dir_path)
        try:
            testfile = tempfile.NamedTemporaryFile("w+t", dir=dir_path)
            print("accesstest", file=testfile)
            testfile.close()
        except (OSError, IOError) as err:
            if err.errno in (errno.EACCES, errno.EEXIST):
                raise OutputDirNotWriteable(dir_path) from err

        # All checks passed so set the output directory
        self._output_dir = dir_path

        if self.verbosity >= 1:
            self.__vo1__(f"Output files will be saved to: {self.output_dir}")

    @property
    def lang(self):
        """Returns the language that has been selected"""
        return self._lang

    @lang.setter
    def lang(self, value):
        """Defines the language to search for"""
        if not value:
            self._lang = ""
            return

        if value in CERTraining.supported_languages:
            self._lang = value
        else:
            raise UnsupportedLanguage(value)

    @property
    def lang_name(self):
        """Return language name"""
        return self.supported_languages[self._lang]["lang_name"]

    @property
    def cer_locale(self):
        """Return CER locale"""
        return self.supported_languages[self._lang]["cer_locale"]

    @property
    def overview_ids(self):
        """Return CSS IDs used for the Overview section on the course website page"""
        return self.supported_languages[self._lang]["overview_ids"]

    @property
    def details_text(self):
        """Returns the text to use for directing the user to the full course details"""
        return self.supported_languages[self._lang]["details_text"]

    @property
    def comment_text(self):
        """Returns text for the comment at the top of the CER file"""
        return self.supported_languages[self._lang]["comment_text"]

    def __red__(self, text):
        """Return text in RED."""
        if self.no_color:
            return text
        return "\033[31m" + text + "\033[0m"

    def __redb__(self, text):
        """Return text in RED BACKGROUND."""
        if self.no_color:
            return text
        return "\033[41m" + text + "\033[0m"

    def __yellow__(self, text):
        """Return text in YELLOW."""
        if self.no_color:
            return text
        return "\033[33m" + text + "\033[0m"

    def __blue__(self, text):
        """Return text in BLUE."""
        if self.no_color:
            return text
        return "\033[34m" + text + "\033[0m"

    def __green__(self, text):
        """Return text in GREEN."""
        if self.no_color:
            return text
        return "\033[32m" + text + "\033[0m"

    def __vo1__(self, text):
        """Returns text for verbosity level 1 output"""
        print(self.__green__(text))

    def __vo2__(self, text):
        """Returns text for verbosity level 2 output"""
        print(self.__yellow__(text))

    def __vo3__(self, text):
        """Returns text for verbosity level 3 output"""
        print(self.__blue__(text))

    def __process_heading__(self, element):
        """Returns asciidoc formatted text for HTML heading tags"""
        return "[.big]#*" + (element.text or "").strip() + "*#"

    def __process_p__(self, element):
        """Returns asciidoc formatted text for HTML paragraph tags"""
        return (element.text or "").lstrip()

    def __process_strong__(self, element):
        """Returns asciidoc formatted text for HTML strong tags"""
        text = ""

        if element.text:
            if element.text.startswith(" ") and element.text.endswith(" "):
                text = " *" + element.text.strip() + "* "
            elif element.text.startswith(" "):
                text = " *" + element.text.lstrip() + "*"
            elif element.text.endswith(" "):
                text = "*" + element.text.rstrip() + "* "
            else:
                text = "*" + element.text + "*"

        return text

    def __process_em__(self, element):
        """Returns asciidoc formatted text for HTML emphasis (e.g. italics) tags"""
        text = ""

        if element.text:
            if element.text.startswith(" ") and element.text.endswith(" "):
                text = " _" + element.text.strip() + "_ "
            elif element.text.startswith(" "):
                text = " _" + element.text.lstrip() + "_"
            elif element.text.endswith(" "):
                text = "_" + element.text.rstrip() + "_ "
            else:
                text = "_" + element.text + "_"

        return text

    def __process_u__(self, element):
        """Returns asciidoc formatted text for HTML underline tags"""
        text = ""

        if element.text:
            if element.text.startswith(" ") and element.text.endswith(" "):
                text = " [.underline]#" + element.text.strip() + "# "
            elif element.text.startswith(" "):
                text = " [.underline]#" + element.text.lstrip() + "#"
            elif element.text.endswith(" "):
                text = "[.underline]#" + element.text.rstrip() + "# "
            else:
                text = "[.underline]#" + element.text + "#"

        return text

    def __process_sub__(self, element):
        """Returns asciidoc formatted text for HTML subscript tags"""
        return "~" + (element.text or "") + "~"

    def __process_sup__(self, element):
        """Returns asciidoc formatted text for HTML superscript tags"""
        return "^" + (element.text or "") + "^"

    def __process_a__(self, element):
        """Returns asciidoc formatted text for HTML link tags"""
        text = ""
        found_href = False

        if element.get("class") == self.image_class:
            return text

        if element.attrib["href"]:
            if element.attrib["href"].startswith("http"):
                text += element.attrib["href"] + "["
                found_href = True

        if element.text:
            text += element.text

        if found_href:
            text += "]"

        return text

    def __process_li__(self, element, level):
        """Returns asciidoc formatted text for HTML ordered and unordered list tags"""
        item_text = ""

        if level == 0:
            level = 1

        if element.getparent().tag.lower() == "ol":
            list_level = "." * level + " "
        else:
            list_level = "*" * level + " "

        if element.text:
            children = element.getchildren()
            children_length = len(children)
            if (children_length == 0 or children_length > 1) or (
                children_length == 1 and children[0].tag.lower() in ["ul", "ol"]
            ):
                item_text += list_level + element.text.lstrip()
            elif children_length == 1 and len(element.text) > 1:
                item_text += list_level + element.text
        else:
            item_text += list_level

        item_text = item_text.replace("\n", "")
        item_text = item_text.replace("\t", "")

        return item_text

    def __process_dt__(self, element):
        """Returns asciidoc formatted text for HTML description list term tags"""
        return (element.text or "").lstrip()

    def __postprocess_dt__(self, level):
        """Returns asciidoc formatted text to complete an HTML description list term tag"""
        text = ""

        if level in [0, 1]:
            text += ":: "
        elif level == 2:
            text += "::: "
        elif level == 3:
            text += ":::: "
        elif level == 4:
            text += ";; "

        return text

    def __process_dd__(self, element):
        """Returns asciidoc formatted text for HTML description list description tags"""
        return element.text or ""

    def __postprocess_dd__(self, element):
        """Returns asciidoc formatted text to complete an HTML description list description tag"""
        text = ""

        # Need to do this because some pages use a definition list (dl) but
        # don't define terms (dt) and only have descriptions (dd)
        # English (en) d0400 was an example of this on 3/27/2022
        prev_tag = element.getprevious()

        if (prev_tag is None) or (prev_tag.tag.lower() != "dt"):
            if element.getnext() is None:
                text += "\n"
            else:
                text += "\n\n"

        return text

    def __process_span__(self, element):
        """Returns asciidoc formatted text for HTML span tags
        Special handling is defined for certain classes"""
        text = ""

        if "class" in element.attrib.keys():
            if element.attrib["class"] == "alert-info-message":
                text += "[IMPORTANT]\n"
                text += "====\n\n"

        if element.text:
            text += element.text.lstrip()

        return text

    def __postprocess_span__(self, element, element_text):
        """Returns asciidoc formatted text to complete an HTML span tag"""
        text = ""

        if not element_text.endswith("\n"):
            if not element_text.endswith("\n\n"):
                text += "\n\n"
            else:
                text += "\n"

        if "class" in element.attrib.keys():
            if element.attrib["class"] == "alert-info-message":
                text += "====\n\n"

        return text

    def __process_br__(self, element):
        """Returns the asciidoc formatted text for HTML br tags"""

        text = ""

        parent_el = element.getparent()
        prev_el = element.getprevious()
        next_el = element.getnext()

        if prev_el is not None and prev_el.tag.lower() == "br":
            prev_tail = str(prev_el.tail or "")
            prev_tail = prev_tail.replace("\n", "")

            if prev_tail:
                text = " +\n"
            else:
                text = "+\n"
        elif parent_el.text and next_el is not None:
            text = " +\n"

        return text

    def __process_element_type__(self, element, level):
        """Returns the asciidoc formatted text of an HTML element type"""
        element_text = ""
        tag = element.tag.lower()

        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            # For the CER we can treat all HTML heading types the same
            element_text += self.__process_heading__(element)
        elif tag == "p":
            element_text += self.__process_p__(element)
        elif tag in ["ul", "ol", "dl"]:
            pass
        elif tag == "li":
            element_text += self.__process_li__(element, level)
        elif tag == "dt":
            element_text += self.__process_dt__(element)
        elif tag == "dd":
            element_text += self.__process_dd__(element)
        elif tag == "strong":
            element_text += self.__process_strong__(element)
        elif tag == "em":
            element_text += self.__process_em__(element)
        elif tag == "u":
            element_text += self.__process_u__(element)
        elif tag == "a":
            element_text += self.__process_a__(element)
        elif tag == "sub":
            element_text += self.__process_sub__(element)
        elif tag == "sup":
            element_text += self.__process_sup__(element)
        elif tag == "span":
            element_text += self.__process_span__(element)
        elif tag == "br":
            element_text += self.__process_br__(element)

        return element_text

    def __process_element__(self, element, level=0):
        """Returns the asciidoc formatted text of an HTML element and its subelements

        This function is called recursively to process each HTML element as it
        is encountered.
        """
        element_text = ""
        tag = element.tag.lower()

        if tag in ["ul", "ol", "dl"]:
            level += 1

        # Get the asciidoc formatted text for the current element before any subelements
        element_text += self.__process_element_type__(element, level)

        # Get the asciidoc formatted text for each subelement
        if element.getchildren():
            for child in element.iterchildren():
                if tag == "li" and child.tag.lower() in ["ul", "ol"]:
                    element_text += "\n"
                # if child.tag.lower() == "br" and element_text == "":
                #     continue
                element_text += self.__process_element__(child, level)

        # After getting the asciidoc text for the element and subelements
        # get any remaining text for the element
        prev_tail = str(element.tail or "")
        prev_tail = prev_tail.replace("\n", "")
        prev_tail = prev_tail.replace("\t", "")

        if not prev_tail.isspace() and prev_tail:
            element_text += prev_tail

        # Add final formatting/processing to ensure the element is properly
        # formatted asciidoc
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            element_text += "\n\n"
        elif tag in ["p"]:
            if element.getparent().tag.lower() != "li":
                element_text = element_text.rstrip()
                if element_text:
                    element_text += "\n\n"
        elif tag in ["ol", "ul", "dl"] and level == 1:
            element_text += "\n"
        elif tag in ["dd"]:
            element_text += self.__postprocess_dd__(element)
            if not element_text.endswith("\n"):
                element_text += "\n"
        elif tag in ["dt"]:
            element_text = element_text.rstrip()
            element_text += self.__postprocess_dt__(level) + "\n"
        elif tag in ["li"] and not element_text.endswith("\n"):
            element_text += "\n"
        elif tag in ["span"]:
            element_text += self.__postprocess_span__(element, element_text)

        return element_text

    def __get_course_details__(self, course):
        """Returns the asciidoc formatted text for a training course"""
        course_url = course["url"]

        # Add any defined comment text to the begging
        cer_text = self.comment_text

        # Get the html page for the course from the website
        try:
            course_details = requests.get(course_url, timeout=30)
            course_details.raise_for_status()
        except requests.exceptions.Timeout as err:
            raise ReadTimeout from err
        except requests.exceptions.TooManyRedirects as err:
            raise TooManyRedirects from err
        except requests.exceptions.RequestException as err:
            error_code = err.response.status_code

            if error_code == 404:
                raise PageNotFound from err

            if error_code == 503:
                raise ServiceUnavailable from err

            raise UnexpectedResponseCode(
                f"Unhandled status code {error_code} returned while querying {course_url}"
            ) from err

        # Parse the returned HTML
        try:
            course_html = html.fromstring(course_details.content, parser=self.html_parser)
        except (ParserError, ParseError) as err:
            if str(err) == 'Document is empty':
                raise EmptyPage() from err
            raise

        # Convert all relative links to absolute links
        course_html.make_links_absolute(base_url="https://www.redhat.com/")

        # Add the asciidoc formatted title and course number
        # The processing here helps to ensure that the title and course number
        # formats are consist across all the asciidoc files (they are not on the website)
        course_num = course_html.find_class(self.c_id_class)
        title_elem = course_html.find_class(self.title_class)
        cer_text += "= "
        if len(title_elem) > 0 and title_elem[0] is not None:
            cer_text += title_elem[0].text.strip()
            if course_num[0] is not None:
                if cer_text.find(course_num[0].text.strip()) < 0:
                    cer_text += " (" + course_num[0].text.strip() + ")"
            cer_text += "\n\n"
        else:
            cer_text += course["title"] + "\n\n"

        # Find the overview section/tab which contains the text needed for the CER
        course_overview = None

        for overview_id in self.overview_ids:
            try:
                course_overview = course_html.get_element_by_id(overview_id)
            except KeyError:
                pass
            if course_overview is not None:
                break

        if course_overview is None:
            raise NoContentFound

        # The overview tab is contained in an HTML div tag that immediately follows
        # the HTML element that contains the overview course_id
        overview_div = course_overview.getnext()

        # Ensure that the element is actually a div tag
        if overview_div.tag.lower() != "div":
            raise NoContentFound

        # Convert the HTML tags for the div subelements into asciidoc
        for element in overview_div.iterchildren():
            # Need to do this because some of the pages do not have well formed HTML
            # and have list elements outside of a list container (e.g. ol or ul)
            prev_element = element.getprevious()
            if prev_element is not None:
                if prev_element.tag.lower() == "li" and element.tag.lower() not in [
                    "ol",
                    "ul",
                    "li",
                ]:
                    cer_text += "\n"

            cer_text += self.__process_element__(element)

        # Replace non-breaking spaces and other unicode/html symbols with AsciiDoc equivalents
        cer_text = cer_text.replace("\xa0", " ")
        cer_text = cer_text.replace("00ae", "(R)")
        cer_text = cer_text.replace("2122", "(TM)")
        cer_text = cer_text.replace("00a9", "(C)")
        cer_text = cer_text.replace("&reg", "(R)")
        cer_text = cer_text.replace("&trade", "(TM)")

        # Ensure the asciidoc text ends with two newlines
        cer_text = cer_text.strip() + "\n\n"

        # Add the wording for getting more details about the course and provide
        # the link to the course
        cer_text += self.details_text + "\n"
        cer_text += course_url + "\n"

        return cer_text

    def find_training(self):
        """Query the Red Hat API to find available training classes"""

        if not self.lang:
            raise NoLanguage

        training_api_url = "https://www.redhat.com/rhdc/jsonapi/solr_search/training"

        query_params = {
            "f[0]": "taxonomy_training_tid:" + self.tid,
            "language": self.lang,
        }

        # The API call returns a lot of data. Only these keys/data are needed
        required_dict_keys = ["courseid", "title", "url", "ds_created"]

        course_dict = {}

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:99.0) "
                "Gecko/20100101 Firefox/99.0"
            )
        }

        course_session = requests.Session()
        course_session.headers.update(headers)

        response = course_session.get(
            "https://www.redhat.com/en/services/training/all-courses-exams"
        )

        if self.verbosity >= 3:
            self.__vo3__("Headers:\n" + str(response.headers) + "\n")

        if self.verbosity >= 3:
            self.__vo3__(
                "Cookies:\n" + json.dumps(course_session.cookies.get_dict(), indent=2)
            )

        # The API returns paginated results so keep getting the next page until
        # there are no more pages to get.
        # The response has how many courses the query has found and what number
        # the current results starts at, so checking the total number found is
        # greater than the starting number plus the number of courses returned
        # in the current results determines when to break out of the
        # endless loop.
        while True:
            if self.verbosity >= 1:
                self.__vo1__(
                    "Obtaining training courses page: "
                    + str(query_params.get("page", 0))
                )

            response = course_session.get(training_api_url, params=query_params)
            response.raise_for_status()

            if self.verbosity >= 3:
                self.__vo3__("Session Headers:\n" + str(course_session.headers) + "\n")
                self.__vo3__(
                    "Cookies:\n"
                    + json.dumps(course_session.cookies.get_dict(), indent=2)
                )
                self.__vo3__(
                    "Response Headers:\n"
                    + json.dumps(dict(response.headers), indent=2)
                    + "\n"
                )

            num_found_classes = len(response.json()["body"]["docs"])

            # Only grab the course data that is needed and add the output filename to use
            # Also keep track of the courses that have already been returned by the API
            #    query so that duplicate results can be detected.
            for course in response.json()["body"]["docs"]:
                if "courseid" in course:
                    c_id = course["courseid"].strip().lower()

                    if c_id not in course_dict:
                        if self.verbosity >= 2:
                            self.__vo2__("Adding Course: " + course["courseid"])

                        course_dict[c_id] = {k: course[k] for k in required_dict_keys}
                        course_dict[c_id]["courseid"] = c_id
                        course_dict[c_id]["filename"] = c_id + ".adoc"
                    else:
                        # If there is a duplicate course found check to determine if it is
                        # newer than the previous course found. If it is then use the data
                        # from the duplicate.
                        if not self.quiet:
                            print(
                                self.__red__(
                                    f"Duplicate Course Returned: {course['courseid']}"
                                )
                            )

                        dup_course = {k: course[k] for k in required_dict_keys}
                        dup_course_dt_str = dup_course["ds_created"]
                        dup_course_dt_obj = datetime.strptime(
                            dup_course_dt_str, "%Y-%m-%dT%H:%M:%SZ"
                        )

                        orig_course_dt_str = course_dict[c_id]["ds_created"]
                        orig_course_dt_obj = datetime.strptime(
                            orig_course_dt_str, "%Y-%m-%dT%H:%M:%SZ"
                        )

                        if dup_course_dt_obj < orig_course_dt_obj:
                            course_dict[c_id] = dup_course
                            course_dict[c_id]["courseid"] = c_id
                            course_dict[c_id]["filename"] = c_id + ".adoc"
                else:
                    print(
                        self.__red__(f"No course course_id was found: {course['url']}")
                    )

            # Increment page number if there are more pages
            if (
                response.json()["body"]["numFound"]
                > response.json()["body"]["start"] + num_found_classes
            ):
                query_params["page"] = query_params.get("page", 0) + 1
            else:
                break

        if self.verbosity >= 2:
            self.__vo2__(
                "Courses Returned: " + str(response.json()["body"]["numFound"])
            )
            self.__vo2__("Courses Added:    " + str(len(course_dict.keys())))

        if self.verbosity >= 3:
            self.__vo3__("Added Courses Detail:" + json.dumps(course_dict, indent=2))

        return list(course_dict.values())

    def update_cer_files(self, all_courses, selected_courses):
        """Updates CER training asciidoc files"""

        # Ensure the language and output directory have been set
        if not self.lang:
            raise NoLanguage

        if not self.output_dir:
            raise NoOutputDir

        if not selected_courses:
            update_all = True
        else:
            update_all = False
            # Ensure list does not have any duplicates and convert to lowercase
            selected_courses = list((map(lambda x: x.lower(), selected_courses)))
            selected_courses = list(set(selected_courses))

        # Making a copy of the courses found so the list doesn't get modified
        # if we found a course that does not have a course details page.
        courses = all_courses.copy()

        for course in courses:
            if not update_all:
                if course["courseid"] not in selected_courses:
                    continue

                selected_courses.remove(course["courseid"])

            if self.verbosity >= 1:
                self.__vo1__("Processing Course: " + course["title"])

            course_text = None

            # Get the asciidoc text to save to the CER course file
            try:
                course_text = self.__get_course_details__(course=course)
            except NoContentFound:
                if not self.quiet:
                    print(
                        self.__red__(f"Unable to find content for: {course['title']}")
                    )
                continue
            except EmptyPage:
                if not self.quiet:
                    print(self.__red__(f"Empty course details returned for: {course['title']}"))
                continue
            except ServiceUnavailable:
                if not self.quiet:
                    print(self.__red__(f"Service Unavailable returned for: {course['title']}"))
                continue
            except PageNotFound:
                if not self.quiet:
                    print(self.__red__(f"Course page not found for: {course['title']}"))

                # Remove the course from the list of courses. This will allow files to be
                # cleaned up if the cleanup option has been selected.
                all_courses.remove(course)
                continue
            except ReadTimeout:
                if not self.quiet:
                    print(self.__red__(f"Timed out getting course data for: {course['title']}"))
                continue
            except TooManyRedirects:
                if not self.quiet:
                    print(self.__red__(f"Redirected too many times while getting course data for: {course['title']}"))
                continue

            # Write the asciidoc course text to the course file
            full_path = self.output_dir + "/" + course["filename"]
            try:
                with open(full_path, "w", encoding="utf-8") as file:
                    file.write(course_text)
                    file.close()
            except IOError as error:
                if error.errno == errno.EACCES:
                    print(self.__red__(f"No permission to write file: {full_path}"))
                    continue

                if error.errno == errno.EISDIR:
                    print(
                        self.__red__(
                            f"Cannot write to file. A directory with the name {full_path} exists"
                        )
                    )
                    continue

        # Notify user that one or more of the requested course updates could not be completed
        if selected_courses:
            if not self.quiet:
                for course_id in selected_courses:
                    print(
                        self.__red__(
                            f"Course {course_id} not found. Check course number."
                        )
                    )

    def cleanup_files(self, found_courses):
        """Removes files for courses not returned by the API query in the output directory"""

        if not self.output_dir:
            raise NoOutputDir

        course_filenames = [course["filename"] for course in found_courses]

        for root, _, files in os.walk(self.output_dir):
            for file in files:
                if file in course_filenames:
                    continue
                if self.verbosity >= 1:
                    self.__vo1__("Removing file: " + os.path.join(root, file))
                os.remove(os.path.join(root, file))


##############################
#
# Main Program
#
##############################


def run_update(training, selected_courses=None):
    """Update courses and handle any errors"""
    if selected_courses is None:
        selected_courses = []

    try:
        # Find all courses
        if not training.quiet:
            print(f"Finding all training courses in {training.lang_name}...")

        all_courses = training.find_training()

        # Update the training content for the found courses
        if not training.quiet:
            print(
                f"Updating {training.lang_name} ({training.cer_locale}) "
                "CER training course files..."
            )

        training.update_cer_files(all_courses, selected_courses)

        # Cleanup the course files for courses that are no longer available
        if training.cleanup:
            if not training.quiet:
                print(
                    f"Cleaning up {training.lang_name} ({training.cer_locale}) "
                    "CER training course files..."
                )
            training.cleanup_files(all_courses)

    except ConnectionError as err:
        if not training.quite:
            print(err)
        if training.debug:
            traceback.print_exc()
        sys.exit(1)

    except Exception as err:  # pylint: disable=broad-except
        if not training.quiet:
            print("Error encountered. Cannot Continue.")
            print(f"Error message : {err}")
        if training.debug:
            traceback.print_exc()
        sys.exit(1)


def process_args(langs):
    """
    Process the command-line arguments
    """
    description = "Gathers training course data for use in the CER"

    parser = argparse.ArgumentParser(description=description)

    output_group = parser.add_mutually_exclusive_group()
    lang_group = parser.add_mutually_exclusive_group()

    lang_group.add_argument(
        "-l",
        "--language",
        action="store",
        dest="lang",
        choices=langs,
        default=langs[0],
        help="Language to search for training classes. Default: %(default)s",
    )

    lang_group.add_argument(
        "-a",
        "--all",
        action="store_true",
        dest="all_langs",
        default=False,
        help="Search all supported languages for training classes. Default: %(default)s",
    )

    parser.add_argument(
        "-c",
        "--course",
        action="append",
        dest="selected_courses",
        metavar="COURSE",
        help=str(
            "Update only selected courses (e.g. rh024). Can be specified "
            "multiple times to update multiple courses.",
        ),
    )
    parser.add_argument(
        "-d",
        "--dir",
        action="store",
        dest="output_dir",
        help="Directory to store output files. The directory must exist and be writeable.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        dest="cleanup",
        default=False,
        help="Remove files from destination directory that are not current training course files",
    )
    parser.add_argument(
        "-n",
        "--no-color",
        action="store_true",
        dest="no_color",
        default=False,
        help="Do not use colored output",
    )

    output_group.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbosity",
        default=0,
        help="Increase the output verbosity",
    )
    output_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        dest="quiet",
        default=False,
        help="Do not display any output",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=False,
        help="Print debug information e.g. a stacktrace when handling an exception",
    )

    return parser.parse_args()


def main():
    """
    Main function
    """
    supported_langs = list(CERTraining.supported_languages.keys())

    args = process_args(supported_langs)

    training = CERTraining(
        no_color=args.no_color,
        verbosity=args.verbosity,
        quiet=args.quiet,
        cleanup=args.cleanup,
        debug=args.debug,
    )

    if args.all_langs:
        for lang in supported_langs:
            training.lang = lang

            dir_full_path = ""

            # Set the output directory to the dir requested by the user or use the
            # default. A language specific dir is created for each language to
            # avoid overwriting.
            if args.output_dir:
                dir_full_path = os.path.abspath(
                    args.output_dir + "/" + training.cer_locale
                )
                if not os.path.isdir(dir_full_path):
                    try:
                        os.makedirs(dir_full_path)
                    except OSError as err:
                        if not args.quiet:
                            print(f"Cannot create directory: {err}")
                        sys.exit(1)

            try:
                training.output_dir = dir_full_path
            except (OutputDirNotFound, OutputDirNotWriteable) as err:
                print(err)
                sys.exit(1)

            run_update(training, args.selected_courses)
    else:
        training.lang = args.lang

        # Set the output directory to the dir requested by the user or use the
        # default
        if args.output_dir:
            try:
                training.output_dir = args.output_dir
            except (OutputDirNotFound, OutputDirNotWriteable) as err:
                print(err)
                sys.exit(1)
        else:
            training.output_dir = ""

        run_update(training, args.selected_courses)


if __name__ == "__main__":
    main()
