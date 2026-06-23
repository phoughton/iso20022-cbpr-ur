
# CBPR Usage Rules validator python package

## Introduction
This package will allow ISO20022 CBPR+ XML messages (used by SWIFT) to be validated against the usage (AKA business) rules that apply to these rules.

These rules are not the same as the XSD rules. These Usage Rules cover things not so easily embodied in XSD files. Also they cover issues that might be across 2 schemas, like between teh message header and the body.

The rules are being updated each year and we have the raw data to build rukles for 2025 and 2026


## Expected usage

A typical user will just want to choose the python package to validate XML files for a given year.

So they should be able to import just one years rules for validation, though they should also be able to import more than one years rules easily.

A couple of was of using the package:

1) The user will import the package and either ask it to read a file or provide it with a string. The package should then provide a dictionary with the relevant violations of the rules.

2) The user can pip install the package and then use it from their CLI as a command line validation tool, where by default the response is textual, and in a human readable list. (though the user could select JSON)

Both methods should have some minimum info for validation errors if found:
- the affected xpath
- affected XML file line number
- description of the issue
- a unique rule number (each rule will have a specific rule number for that message type)

Some files provided for validation will need have different wrapper tags (e.g.: <RequestDocuument>,<Payload> etc ), ensure the system is flexible enough to ignore these unless they break the rules.

## How are the rules created?

The analysis of the raw rules should be done with maximum reasoning, its important we use all possible intellegence as this is the core of the system.

The package will require rules to be extracted from prose and pseudo code held in spreadsheets.

The rules should be examined, clarified (its OK to ask questions) and embodied in python code.

A rule should be created even if there is no pseudo code in the spreadsheet for rules.

Try and make a rule where possible.

Some ISO20022 CBPR+ message rules might be across 2 raw files (the one for the header and the one for the body) so this something to be aware of.

Some rules may be common across different file types e.g. PACS008 and PACS009

If in doubt the ISO20022 defaults are a sensible back stop.

## The raw files

The raw files are located in year dated folders:
raw_rules_files/2025
raw_rules_files/2026

And below there in folders for the messge type & number e.g: PAIN008 etc 

## XSDs

The XSD files are provided for informational purposes and we are not trying to duplicate their logic or incorporate them.

## Documentation

The README should include:
- install guide
- a quick start guide.
- relevant mid-level usage details
- a more indepth usage section
- A note that the code is AI generated

## Specific validations

Some validations are not in the rules, for example:
- LEI codes
- IBANs

For these use the relevant algorithms, e.g.:
- IBAN https://en.wikipedia.org/wiki/International_Bank_Account_Number
- LEI https://en.wikipedia.org/wiki/Legal_Entity_Identifier

Country codes should also be valid: https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes

If there are fields that probably require validation but are not mentioned here, use wikipedia and if that is not comprehensive enough, ask.
