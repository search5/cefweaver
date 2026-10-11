"""Printing from cefweaver on macOS.

On macOS CEF has no ``PrintHandler`` (it is for Linux): ``host.print()`` opens the print panel of the system, as a modal
window, and the system does the rest (printer, paper, copies, page range, "Save as PDF"). The application writes no
dialog and ``printing.py`` (CUPS, a Tk dialog) is not used.

For a job without that panel, or with settings the application chooses, the page goes through a PDF:

* ``save_pdf()``       CEF makes the PDF (``host.print_to_pdf()``: paper, orientation, background);
* ``print_with_system()``  the PDF goes to the print system with ``NSPrintOperation`` (PDFKit), with or without the
  panel, to a printer of the system or to a file;
* ``lp_command()`` / ``send_with_lp()``  the PDF goes to CUPS (macOS is built on it) with ``lp``, the same way as on Linux.

Needs PyObjC (``pyobjc-framework-Quartz``).
"""

import os
import re
import subprocess

from AppKit import (NSApplication, NSPrintCopies, NSPrintInfo, NSPrintJobDisposition, NSPrintJobSavingURL,
                    NSPrinter, NSPrintSaveJob)
from Foundation import NSURL
from Quartz import PDFKit

import cefweaver
from cefweaver import types

SWITCHES = []                       # nothing is needed (Linux needs disable-features=EnableOopPrintDrivers)

# The sizes CEF's print_to_pdf() takes, in inches.
PAPERS = {"A4": (8.27, 11.69), "A5": (5.83, 8.27), "Letter": (8.5, 11.0), "Legal": (8.5, 14.0)}


# -- the print system ----------------------------------------------------------------------------------------------

def printers():
    """The names of the destinations of CUPS, those added and those it found on the network (``lpstat -e``)."""
    result = subprocess.run(["lpstat", "-e"], capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def default_printer():
    """The default destination of the system, or ``None`` (the text of ``lpstat -d`` depends on the language of the
    system; with a default it ends in ``: name``)."""
    result = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
    found = re.search(r":\s*(\S+)\s*$", result.stdout.strip())
    return found.group(1) if found else None


# -- the PDF -------------------------------------------------------------------------------------------------------

def pdf_settings(paper="A4", landscape=False):
    """The settings of ``print_to_pdf()``. The paper is given upright and ``landscape`` turns it: CEF does that
    itself (swapping the sides as well would turn the page twice and give a portrait page)."""
    width, height = PAPERS[paper]
    return types.PdfPrintSettings(landscape=landscape, print_background=True, scale=1.0,
                                  paper_width=width, paper_height=height)


class _Finished(cefweaver.PdfPrintCallback):
    def __init__(self, done):
        super().__init__()
        self.done = done

    def on_pdf_print_finished(self, path, ok):
        self.done(path, ok)


def save_pdf(host, path, done, paper="A4", landscape=False):
    """Let CEF write the page to the PDF ``path``; ``done(path, ok)`` is called on the thread of CEF when it is
    written. Works with an offscreen browser too. (Nothing like ``PrintHandler.get_pdf_paper_size`` is needed.)"""
    if os.path.exists(path):
        os.remove(path)
    host.print_to_pdf(path, pdf_settings(paper, landscape), _Finished(done))


def pdf_info(path):
    """``(pages, width_pt, height_pt)`` of the first page of a PDF."""
    document = PDFKit.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(path))
    page = document.pageAtIndex_(0)
    box = page.boundsForBox_(PDFKit.kPDFDisplayBoxMediaBox)
    return document.pageCount(), box.size.width, box.size.height


# -- the PDF to the print system -----------------------------------------------------------------------------------

def print_with_system(pdf_path, copies=1, printer=None, show_panel=False, save_to=None):
    """Print the PDF with ``NSPrintOperation``. ``show_panel``: the print panel of the system for this PDF (modal,
    the call returns when it is closed). ``save_to``: a file instead of a printer (the job is "save as PDF"; for a
    test without paper). ``printer``: the name of a printer of the print system (``NSPrinter``): a destination that
    CUPS only found on the network is not one of them, use ``send_with_lp()`` for it. Returns whether the job was
    done."""
    NSApplication.sharedApplication()
    info = NSPrintInfo.sharedPrintInfo().copy()      # the defaults of the user; an empty NSPrintInfo has no paths
    settings = info.dictionary()
    settings[NSPrintCopies] = copies
    if save_to:
        settings[NSPrintJobDisposition] = NSPrintSaveJob
        settings[NSPrintJobSavingURL] = NSURL.fileURLWithPath_(save_to)
    elif printer:
        chosen = NSPrinter.printerWithName_(printer)
        if chosen is None:
            raise ValueError("%r is not a printer of the print system" % printer)
        info.setPrinter_(chosen)
    document = PDFKit.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(pdf_path))
    operation = document.printOperationForPrintInfo_scalingMode_autoRotate_(info, PDFKit.kPDFPrintPageScaleToFit, True)
    operation.setShowsPrintPanel_(show_panel)
    operation.setShowsProgressPanel_(False)
    return bool(operation.runOperation())


def lp_command(pdf_path, printer, copies=1, paper_name="A4", landscape=False):
    """The ``lp`` command line for the PDF: the copies and the paper are options of the job."""
    command = ["lp", "-d", printer, "-n", str(copies), "-o", "media=" + paper_name]
    if landscape:
        command += ["-o", "orientation-requested=4"]
    return command + [pdf_path]


def send_with_lp(pdf_path, printer, copies=1, paper_name="A4", landscape=False, really=False):
    """``lp`` for the PDF. Without ``really`` nothing is sent: the command is returned (a dry run). With it the
    ``CompletedProcess`` of ``lp`` is returned and the printer prints."""
    command = lp_command(pdf_path, printer, copies, paper_name, landscape)
    if not really:
        return command
    return subprocess.run(command, capture_output=True, text=True)
