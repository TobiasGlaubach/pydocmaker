I have prepared a cli.py file in src. 

for the cli file please write a cli gateway for my pydocmaker library and update the pyproject.toml file accordinly, so the user can call 


e.g.

"pydocmaker build "README.md"

or 

"pydocmaker build "my_report.tex"


please use the standard argparse and write extensive documentation.

The groups shall be:

"example" --> with a given format and a given output string after "-o" (empty for print to stdout) which writes a doc.get_example() example in a format to the given filepath or stdout.

"show" --> with a given format and an input file which shows either the input file or doc.get_example() using doc.show().

"build" --> reads documents and makes them into a given output format (by default PDF) out filename shall be the same as in filename but with a different file extension. 
allowed to read shall be json pydocmaker file (see Doc.save and Doc.load), html pydocmaker file (html_loader.py), markdown, or latex, any other non binary document shall be read as text and parsed in the document via add_text

"convert" --> synonym for build

"check" --> recks the syntax of a passed input file which can be one of the following:
- json pydocmaker file --> states whether or not the syntax is OK
- html pydocmaker file (html_loader.py) --> states whether or not the syntax is OK
- a "blocktemplate" file of either HTML, tex, or typ  --> analyzes the blocks, checks for correctness, finds parameters and prints parameters as JSON

"extract" --> extracts parameters from a given template file and prints parameters as JSON

"template" --> with a given input string and a given output string after "-o" (empty for print to stdout) which can be either "html", "tex", or "typ" or e.G. "base.html" which will copy the new template to a given output file location, or show it on stdout. If no base filename is given it shall default back "base.XXX"



=================================




Please look @src/pydocmaker/templates/report.typ and @src/pydocmaker/templates/base.tex please make a tex based report template in @src/pydocmaker/templates/report.tex. 

you can also look at the file "/home/tglaubach/mpifr-tdd-document-templates/latex-typst/tdd-template-report.tex" for some guidance on complex tex templates.

please make sure they are functionally the same and look similar. no need to match exactly, but they should have a very similar look. 