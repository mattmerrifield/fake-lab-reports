import enum
import itertools
import platform
import random
import datetime as dt
import statistics
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

import pdfkit

from jinja2 import Template

if platform.system() == "Windows":
    # ugh. Sorry. I need a better OS on this box, but this is a quick dirty hack
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    PDF_CONFIG = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
else:
    PDF_CONFIG = pdfkit.configuration()

TEMPLATES = Path(__file__).parent

with open(TEMPLATES / "template.jinja2") as fh:
    template = Template(source=fh.read())

# The probability any given test will fall within the "normal" range
P_PASS = 0.8

# Some numbers are formatted as a single decimal
ONE_DECIMAL = "{:0.1f}"

@dataclass
class Between:
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

    def sample(self, rand_seed, p_pass) -> 'Sample':
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
        z_top = dist.inv_cdf((1 + p_pass)/2)

        # He who controls the spice controls the universe.
        # By spice I mean psuedo-random number generator seed.
        z_sample = dist.samples(1, seed=rand_seed)[0]
        print(f"{z_sample}/{z_top}")
        allowed_deviation = abs(mean - self.high)
        actual_deviation = z_sample * allowed_deviation / z_top
        val = mean + actual_deviation

        return Sample(
            range=self,  # Contains formatting directives, and in/out of bounds info
            val=val,
        )

    def check_bounds(self, val: float) -> str:
        out_of_range = self.contains(val)
        if out_of_range == Between.BELOW:
            return f"L"
        if out_of_range == Between.ABOVE:
            return f"H"
        return ""

    def contains(self, value):
        # The value is called out with a prefix if it's too high or too low
        if self.low < value < self.high:
            return self.OK
        if value < self.low:
            return Between.BELOW
        if self.high < value:
            return Between.ABOVE


@dataclass
class LTHigh(Between):
    """
    Expect below. Must provide low anyway, so we can generate a number
    """
    fmt_range: str = "<{high}"

    def contains(self, value):
        if self.high < value:
            return Between.ABOVE
        return Between.OK


@dataclass
class GTLow(Between):
    """
    Expect above. Must provide high anyway, so we can generate a number
    """
    fmt_range: str = ">{low}"

    def contains(self, value):
        if value < self.low:
            return Between.BELOW
        return Between.OK


@dataclass
class Sample:
    """
    The result of sampling a range, formatted according to that range's conventions.
    """
    range: Between
    val: float  # pre-formatted for precision

    @property
    def value(self):
        precision = self.range.fmt_precision.format(self.val)
        final = self.range.fmt_result.format(precision)
        return final

    @property
    def ok(self):
        return self.range.check_bounds(self.val)



@dataclass
class Test:
    """
    Quantitative description of a diagnostic test to run, including name, expected range, units, etc.
    """
    # Parameters to generate a test result.
    name: str
    range: Between
    units: str

    def sample(self, rand_seed, p_pass) -> 'Result':
        """
        Psuedo-random result generator
        """
        return Result(
            test=self,
            result=self.range.sample(rand_seed, p_pass)
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
        results: List[Result] = [t.sample(not_rand.randint(0, sys.maxsize), instance.p_pass) for t in self.tests]
        for r in results:
            if val := instance.override_samples.get(r.test.name, None):
                r.result.val = val
        return results


@dataclass
class LabReport:
    """
    Fake data for a fake lab report
    """
    # Configurable report parameters
    patient_number: int
    collected_at: dt.datetime
    has_disease: bool
    p_pass: float = P_PASS
    override_samples: dict = field(default_factory=dict)

    # Data descriptor for making a list of fake test results.
    # Use it like a property, e.g. `results = self.metabolic_panel`
    metabolic_panel = GenList(
        Test("Sodium", Between(132, 146), "mM"),
        Test("Potassium", Between(3.4, 5.4, fmt_precision=ONE_DECIMAL), "mM", ),
        Test("Chloride", Between(99, 109), "mM"),
        Test("Bicarbonate", Between(19, 33), "mM"),
        Test("Glucose", Between(73, 105, fmt_result="{}**"), "mg/dL"),
        Test("Bun", Between(6, 24), "mg/dL", ),
        Test("Creatine", Between(0.5, 1.2, fmt_precision=ONE_DECIMAL), "mg/dL", ),
        Test("Calcium", Between(8.3, 10.6, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Protein, Total", Between(6, 8, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Albumin", Between(3.5, 5.1, fmt_precision=ONE_DECIMAL), "g/dL", ),
        Test("Bilirubin, Total", Between(0.3, 1.4, fmt_precision=ONE_DECIMAL), "mg/dl", ),
        Test("ALP", Between(44, 135), "U/L", ),
        Test("ALT", Between(7.9, 40.9, fmt_precision=ONE_DECIMAL), "U/L"),
        Test("AST", Between(0, 35), "U/L"),
    )

    lipid_panel = GenList(
        Test("Cholesterol, Total", LTHigh(100, 240), "mg/dL"),
        Test("Triglycerides", LTHigh(100, 200), "mg/dL"),
        Test("HDL Cholesterol", GTLow(40, 90), "mg/dL"),
        Test("LDL Cholesterol", LTHigh(85, 130), "mg/dL"),
    )

    def force_result(self, name, value):
        """
        Force a specific test, by name, to have a specific value
        """
        # Ew, gross, just us a hash map why don't you (because this is a hack job)
        for t in itertools.chain(self.metabolic_panel, self.lipid_panel):
            if t.test.name == name:
                t.result.value = value
                return
        raise KeyError(f"Test {name} not found")


    def as_html(self) -> str:
        """
        use the above template to get an HTML report
        """
        ctx = asdict(self)
        ctx['metabolic_panel'] = self.metabolic_panel
        ctx['lipid_panel'] = self.lipid_panel
        ctx['has_disease'] = self.has_disease
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


def generate(patient_number, output_folder, has_disease, p_pass):
    r = LabReport(patient_number=patient_number, collected_at=dt.datetime.now(), has_disease=has_disease, p_pass=p_pass)
    out = Path(output_folder) / f"{patient_number}.pdf"
    r.save_pdf(out)


def gen_samples():
    output_folder = Path(__file__).parent / "okay"
    output_folder.mkdir(exist_ok=True)

    START_AT = 15900
    NUM_REPORTS = 60

    # Arbitrary range of patient numbers; all healthy
    for i, patient_number in enumerate(range(START_AT, START_AT + NUM_REPORTS)):
        r = LabReport(patient_number=patient_number, collected_at=dt.datetime.now(), has_disease=False, p_pass=P_PASS)
        out = Path(output_folder) / f"report-{i}.pdf"
        # r.save_pdf(out)

    # One bad patient, with ID 10
    BAD_ID = 10
    output_folder = Path(__file__).parent / "bad"
    output_folder.mkdir(exist_ok=True)
    r = LabReport(patient_number=START_AT + BAD_ID, collected_at=dt.datetime.now(), has_disease=True, p_pass=P_PASS/2)

    # Some specific hard-coded changes for this one
    r.override_samples = {
        'Sodium': 162,
        'Potassium': 6.8,
        "Bicarbonate": 40,
        "Chloride": 118,
        'Glucose': 152,
        'Bun': 41,
        'Creatine': 1.44,
        'Calcium': 15,
        'Protein, Total': 6.6,
        'Albumin': 33,
        'Bilirubin, Total': 2.4,
        "ALP": 188.8,
        'ALT': 31,
        'AST': 93,
        "Cholesterol, Total": 259,
        "Triglycerides": 213,
        "HDL Cholesterol": 22,
        "LDL Cholesterol": 158,
    }

    out = Path(output_folder) / f"report-{BAD_ID}.pdf"
    r.save_pdf(out)



if __name__ == "__main__":
    gen_samples()

    import argparse, sys

    parser = argparse.ArgumentParser()
    parser.add_argument('patient_number', action='store')
    parser.add_argument('--output_folder', '-o', type=str, default='.')
    parser.add_argument('--has_disease', '-d', action='store_true')

    args = parser.parse_args(sys.argv[1:])

    generate(args.patient_number, args.output_folder, args.has_disease, P_PASS/2 if args.has_disease else P_PASS)
