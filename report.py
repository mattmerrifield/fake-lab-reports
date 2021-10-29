import enum
import random
import datetime as dt
import statistics
import sys
from dataclasses import dataclass, asdict
from typing import List, Optional

from xhtml2pdf import pisa

from jinja2 import Template

# language=jinja2
template = Template(source="""
<html>
<style>
p {
  font-size: 10;
}

tbody {
  font-size: 10
}

* {
  font-family: "Gill Sans", sans-serif;
}

h1 {
  color: grey;
}

.report {
  width: 7in;
  height: 10.1in;
  border: 2px solid black;
  margin: 50px;
  padding: 10px;
}

.subtitle {
  text-align: center;
  font-weight: bold;
  font-size: 14;
}

.subtitle {
  margin-bottom: 20px;
  text-align: center;
}

.sender {
  padding-bottom: 2px;
  margin-bottom: 0;
  
}

.letterhead {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid green;
  margin-bottom: 10px;
  padding-bottom: 2px;
}

.letterhead > p {
  padding-bottom: 0;
  margin-bottom: 0;
}

.send-date {
  justify-self: right;
}

.footer-break {
  border-top: 2px solid green;
  border-bottom: 2px solid green;
  height: 10px;
}
.footer > p {
  padding: 0;
  margin: 0;
}
.section-header {
  background: #d2e6c3;
  border: 1px solid black;
  padding: 4px;
}

th {
  border: 1px solid black;
  font-weight: normal;
  text-align: left;
}

.report-meta > tbody > tr> th {
  padding-left: 20px;
  min-width: 220px;
}

td {
  padding-left: 20px;
}

.test-results > tbody > tr > td {
  
}

.test-results >tbody > tr > td {
  min-width: 1.5in
}
.units {
  align-content: left;
  padding-left: 0;
}

.result {
  text-align: center;
}

.range {
  text-align: center;
}

.footer {
  display: flex;
  justify-content: space-between;
}
</style>
<div class=report>
    <h1>theranos</h1>
    <p class='subtitle'>Theranos Test Report Technology Demonstration</p>
    <p class='sender'>Theranos, Inc.</p>
    <div class='letterhead'>
        <p class='address'>1601 S. California Ave, Palo Alto CA 94304</p>
        <p class='send-date'>{{ collected_at.date() }}</p>
    </div>
    <div class='section-header'>
        <p>PATIENT INFORMATION</p>
    </div>
    <table class='report-meta'>
        <tr>
            <th>PATIENT NO.</td>
            <td>{{ patient_number }}</td>
        </tr>
        <tr>
            <th>D.O.B.</th>
            <td>Unknown</td>
        </tr>
        <tr>
            <th>AGE/GENDER</th>
            <td>N/A / M</td>
        </tr>
        <tr>
            <th>PT MEDICATIONS</th>
            <td>Unknown</td>
        </tr>
        <tr>
            <th>ORDERING M/D</th>
            <td>Dr. Elizabeth Holmes, Vmp.</td>
        </tr>
    </table>
    <div class='section-header'>
        <p>TEST DETAIL</p>
    </div>
    <table class='report-meta'>
        <tr>
            <th>DATE COLLECTED</th>
            <td>{{ collected_at.date() }}</td>
        </tr>
        <tr>
            <th>SPECIMEN(S) COLLECTED</td>
            <td>Blood</td>
        </tr>
        <tr>
            <th>DATE REPORTED</th>
            <td>{{ collected_at.date() }}</td>
        </tr>
        <tr>
            <th>COMMENTS</th>
            <td>Non-fasting *Organ Transplant Qualification*</td>
        </tr>
    </table>
    <div class='section-header'>
        <p> COMPREHENSIVE METABOLIC PANEL</p>
    </div>
    <table class="test-results">
        <tr class='test-results-header'>
            <th>TEST NAME</th>
            <th>PATIENT's RESULTS</th>
            <th>REF. RANGE</th>
            <th>UNITS</th>
        </tr>
        {% for r in metabolic_panel %}
        <tr>
            <td class='name'>{{ r.test.name }}</td>
            <td class='result'>{{ r.result }}</td>
            <td class='range'>{{ r.test.range }}</td>
            <td class='units'>{{ r.test.units }}</td>
        </tr>
        {% endfor %}
    </table>
    <p>Key: L= Below Reference Range, H = Above Reeference Range, WNL = Within Normal Limits, * = Critical Value</p>
    <p>** Reference range is for fasting; results can fluctuate outside of this range based on fasting state</p>
    
    <div class='section-header'>
        <p>LIPID PANEL</p>
    </div>
    
    <table class="test-results">
        <tr class='test-results-header'>
            <th>TEST NAME</th>
            <th class='result'>PATIENT's RESULTS</th>
            <th class='range'>REF. RANGE</th>
            <th>UNITS</th>
        </tr>
        {% for r in lipid_panel %}
        <tr>
            <td class='name'>{{ r.test.name }}</td>
            <td class='result'>{{ r.result }}</td>
            <td class='range'>{{ r.test.range }}</td>
            <td class='units'>{{ r.test.units }}</td>
        </tr>
        {% endfor %}
    </table>
    <p>Key: L= Below Reference Range, H = Above Reeference Range, WNL = Within Normal Limits, * = Critical Value</p>
    
    <div class='footer-break'></div>
    
    <p style='text-align:center'>End of Report</p>
    <div class='footer'>
        <p>Anonymous Guest</p>
        <p>Patient No. {{ patient_number }}</p>
        <p>{{ collected_at.date() }}</p>
    </div>
</div>
</html>
""")

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
            value=val,
        )

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
    value: float  # pre-formatted for precision

    def __str__(self):
        # The range and value have the same decimal precision
        num = self.range.fmt_precision.format(self.value)
        # The value might have a standard prefix or postfix
        val = self.range.fmt_result.format(num)
        out_of_range = self.range.contains(self.value)
        if out_of_range == Range.BELOW:
            return f"L {val}"
        if out_of_range == Range.ABOVE:
            return f"H {val}"
        return val


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
        Test("Protein, Total", Range(6, 8), "g/dL", ),
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
        print(ctx)
        return template.render(ctx)

    def save_html(self, filename):
        with open(filename, 'w') as fh:
            fh.write(self.as_html())

    def save_pdf(self, filename):
        """
        Generate psuedorandom results, and render them as a PDF
        """
        with open(filename, 'wb') as fh:
            pisa.CreatePDF(
                src=self.as_html(),
                dest=fh,
            )


if __name__ == "__main__":
    r = LabReport(patient_number=12345, collected_at=dt.datetime.now())
    r.save_pdf("test.pdf")
    r.save_html("test.html")


