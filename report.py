from xhtml2pdf import pisa
from jinja2 import Template
from dataclasses import dataclass, asdict

template = Template(source="""
<h1>Hello World!</h1>
<p>Report Number: {{ report_number }}</p>
""")

@dataclass
class LabReport:
    """
    Fake data for a fake lab report
    """
    report_number: int

    def save(self, filename):
        """
        Save a new report PDF file with this chunk of data
        """
        filled_report = template.render(**asdict(self))
        with open(filename, 'wb') as fh:
            pisa.CreatePDF(
                src=filled_report,
                dest=fh,
            )


if __name__ == "__main__":
    r = LabReport(report_number=12345)
    r.save("test.pdf")


