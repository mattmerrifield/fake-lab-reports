import enum
import platform
import random
import datetime as dt
import statistics
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import pdfkit

from jinja2 import Template

# ugh. Sorry. I need a better OS on this box, but this is a quick dirty hack
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
PDF_CONFIG = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf,)

TEMPLATES = Path(__file__).parent

with open(TEMPLATES / "template.jinja2") as fh:
    template = Template(source=fh.read())

# The probability any given test will fall within the "normal" range
P_PASS = 0.8

# Some numbers are formatted as a single decimal
ONE_DECIMAL = "{:0.1f}"

@dataclass
class Range:
    """
    The normal range of a test result.
    """
    low: float
    high: float
    fmt_precision: str = "{:0.0f}"
    fmt_result: str = "{}"  # extra stuff on the report?
    fmt_range: str = "{low} - {high}"

    BELOW = -1
    OK = 0
    ABOVE = 1

    def __str__(self):
        """
        String representation of the range itself
        """
        high, low = self.fmt_precision.format(self.high), self.fmt_precision.format(self.low)
        return self.fmt_range.format(high=high, low=low)

    def sample(self, rand_seed) -> 'Sample':
        """
        Use a specific seed to deterministically generate a random-looking result within (or slightly out of) the
        expected high/low range
        """
        # Bad assumption: average Americans have metabolic panel values in the middle of the range. Haha what a joke.
        mean = (self.high + self.low) / 2

        # Math problem: What standard deviation would give us an out-of-range value `failure_pct` of the time?
        # Work backwards from z-score P values, and the fact that 1-sigma is 68%.
        # TODO: implement bias by messing with this distribution function.
        dist = statistics.NormalDist(0, 1)
        z_top = dist.inv_cdf((1 + P_PASS)/2)

        # He who controls the spice controls the universe.
        # By spice I mean psuedo-random number generator seed.
        z_sample = dist.samples(1, seed=rand_seed)[0]
        print(f"{z_sample}/{z_top}")
        allowed_deviation = abs(mean - self.high)
        actual_deviation = z_sample * allowed_deviation / z_top
        val = mean + actual_deviation

        return Sample(
            range=self,  # Contains formatting directives, and in/out of bounds info
            value=self._fmt(val),
            ok=self.check_bounds(val)
        )

    def _fmt(self, val: float) -> str:
        """
        Format as a string for display
        """
        precision = self.fmt_precision.format(val)
        final = self.fmt_result.format(precision)
        return final

    def check_bounds(self, val: float) -> str:
        out_of_range = self.contains(val)
        if out_of_range == Range.BELOW:
            return f"L"
        if out_of_range == Range.ABOVE:
            return f"H"
        return ""

    def contains(self, value):
        # The value is called out with a prefix if it's too high or too low
        if self.low < value < self.high:
            return self.OK
        if value < self.low:
            return Range.BELOW
        if self.high < value:
            return Range.ABOVE


@dataclass
class Below(Range):
    """
    Expect below. Must provide low anyway, so we can generate a number
    """
    fmt = "<{high}"

    def contains(self, value):
        if self.high < value:
            return Range.ABOVE
        return Range.OK


@dataclass
class Above(Range):
    """
    Expect above. Must provide high anyway, so we can generate a number
    """
    fmt = ">{low}"

    def contains(self, value):
        if value < self.low:
            return Range.BELOW
        return Range.OK


@dataclass
class Sample:
    """
    The result of sampling a range, formatted according to that range's conventions.
    """
    range: Range
    value: str  # pre-formatted for precision
    ok: str



@dataclass
class Test:
    """
    Quantitative description of a diagnostic test to run, including name, expected range, units, etc.
    """
    # Parameters to generate a test result.
    name: str
    range: Range
    units: str

    def sample(self, rand_seed) -> 'Result':
        """
        Psuedo-random result generator
        """
        return Result(
            test=self,
            result=self.range.sample(rand_seed)
        )


@dataclass
class Result:
    """
    The sampled result of a test
    """
    test: Test
    result: Sample


class GenList:
    """
    Data descriptor to get random data from bunch of test data generators

    Alsa a data attribute to generate a Result
    """

    def __init__(self, *generators):
        self.tests = generators

    def __get__(self, instance: 'LabReport', owner) -> List['Result']:
        """
        Render a result based on the lab report's patient number. Should be random-looking, but deterministic based
        on the patient number. Result includes test meta-data like expected reference range, test name, etc. It's
        ready to render on a template.
        """
        # Use the patient's ID number as a random seed. Same person, same results. Every time.
        # Good point of argument for skeptical patients.
        # But don't use the literal same seed value for every sample -- use a deterministic array of them, so
        # they're each in or out of range independently of one another
        not_rand = random.Random(instance.patient_number)
        return [t.sample(not_rand.randint(0, sys.maxsize)) for t in self.tests]


@dataclass
class LabReport:
    """
    Fake data for a fake lab report
    """
    # Configurable report parameters
    patient_number: int
    collected_at: dt.datetime

    # Data descriptor for making a list of fake test results.
    # Use it like a property, e.g. `results = self.metabolic_panel`
    metabolic_panel = GenList(
        Test("Sodium", Range(132, 146), "mM"),
        Test("Potassium", Range(3.4, 5.4, fmt_precision=ONE_DECIMAL), "mM", ),
        Test("Chloride", Range(99, 109), "mM"),
        Test("Bicarbonate", Range(19, 33), "mM"),
        Test("Glucose", Range(73, 105, fmt_result="{}**"), "mg/dL"),
        Test("Bun", Range(6, 24), "mg/dL", ),
        Test("Creatine", Range(0.5, 1.2, fmt_precision=ONE_DECIMAL), "mg/dL", ),
        Test("Calcium", Range(8.3, 10.6, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Protein, Total", Range(6, 8, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Albumin", Range(3.5, 5.1, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Bilirubin, Total", Range(0.3, 1.4, fmt_precision=ONE_DECIMAL), "mg/dl", ),
        Test("ALT", Range(44, 135), "U/L", ),
        Test("ALT", Range(7.9, 40.9, fmt_precision=ONE_DECIMAL), "U/L"),
        Test("AST", Range(0, 35), "U/L"),
    )

    lipid_panel = GenList(
        Test("Cholesterol, Total", Below(0, 240), "mg/dL"),
        Test("Triglycerides", Below(0, 200), "mg/dL"),
        Test("HDL Cholesteral", Below(0, 40), "mg/dL"),
        Test("LDL Cholesterol", Above(130, 260), "mg/dL"),
    )

    def as_html(self) -> str:
        """
        use the above template to get an HTML report
        """
        ctx = asdict(self)
        ctx['metabolic_panel'] = self.metabolic_panel
        ctx['lipid_panel'] = self.lipid_panel
        # PDF requires inline style sheets, which we inject via templating
        with open(TEMPLATES / "style.css") as fh:
            ctx['style'] = fh.read()
        with open(TEMPLATES / "normalize.css") as fh:
            ctx['normalize'] = fh.read()
        print(ctx)
        return template.render(ctx)

    def save_html(self, filename):
        with open(filename, 'w') as fh:
            fh.write(self.as_html())

    def save_pdf(self, filename):
        """
        Generate psuedorandom results, and render them as a PDF
        """
        pdfkit.from_string(
            self.as_html(), filename, configuration=PDF_CONFIG,
            options={
                'encoding': "UTF-8",
                'print-media-type': '',
                'page-size': 'A4',
                'zoom': '1.1'
            }
   )

def generate(patient_number, output_folder):
    r = LabReport(patient_number=patient_number, collected_at=dt.datetime.now())
    out = Path(output_folder) / f"{patient_number}.pdf"
    r.save_pdf(out)



if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser()
    parser.add_argument('patient_number', action='store')
    parser.add_argument('--output_folder', '-o', type=str, default='.')

    args = parser.parse_args(sys.argv[1:])

    generate(args.patient_number, args.output_folder)



