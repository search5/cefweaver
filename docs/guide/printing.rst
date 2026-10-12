Printing and PDF
================

Two things are called printing. Saving what a browser shows as a PDF file is one call on the browser host (:meth:`~cefweaver.BrowserHost.print_to_pdf`) and needs nothing else. Sending a page to a printer is different: on Linux CEF has no print dialog and no list of printers, so the application provides both through a :class:`~cefweaver.PrintHandler`. The differences on Windows and macOS are in :doc:`limitations` and are not repeated here.

Everything on this page was run with the installed wheel (CEF 154) on Linux x86_64, with an offscreen browser on a virtual X server. Each output shown is the output of three runs in a row. Window mode was not tried, and no paper was printed: the print handler example copies the PDF and finishes the job without sending it anywhere.

Save a page as PDF
------------------

:meth:`~cefweaver.BrowserHost.print_to_pdf` takes the output path, a :class:`~cefweaver.types.PdfPrintSettings` and a :class:`~cefweaver.PdfPrintCallback` (or ``None``). The callback is called as ``on_pdf_print_finished(path, ok)`` from the message loop. The script below loads a three page document from memory, saves it with several settings and reads each file back:

.. literalinclude:: recipes/print_pdf.py
   :language: python

Run on a virtual X server (``xvfb-run -a python -P print_pdf.py``) it prints:

.. code-block:: text

   default: ok=True (b'%PDF-', 3, 612.0, 792.0)
   a4-landscape: ok=True (b'%PDF-', 6, 841.92, 595.92)
   page 2 only: ok=True (b'%PDF-', 1, 612.0, 792.0)
   pages 2-9: ok=True (b'%PDF-', 2, 612.0, 792.0)
   page 9: ok=False no file: True
   3-1: ok=False no file: True
   missing folder: ok=False no file: True

The fields are (name, type and meaning are from the docstring of :class:`~cefweaver.types.PdfPrintSettings`):

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Meaning
   * - ``landscape``
     - Landscape instead of portrait.
   * - ``paper_width``, ``paper_height``
     - The paper in inches. If either is zero or less, the default (Letter, 8.5 x 11 inches) is used. All fields at their defaults gave a 612 x 792 pt page above.
   * - ``scale``
     - Zoom of the content; zero or less means 1.0.
   * - ``prefer_css_page_size``
     - Use the page size of the CSS ``@page`` rule. Otherwise the content is scaled to fit the paper.
   * - ``margin_type``
     - A :class:`~cefweaver.types.PdfPrintMarginType`: ``DEFAULT`` (1 cm), ``NONE`` or ``CUSTOM``. ``margin_top``, ``margin_right``, ``margin_bottom`` and ``margin_left`` (inches) are used with ``CUSTOM`` only.
   * - ``page_ranges``
     - A string such as ``"1-5, 8, 11-13"``, **one based**. The pages come in document order. A range past the end is cut to the page count; a range that leaves no page, or one with its start after its end, is an error.
   * - ``print_background``
     - Print background colors and images.
   * - ``display_header_footer``, ``header_template``, ``footer_template``
     - A header and a footer from HTML templates. The classes ``date``, ``title``, ``url``, ``pageNumber`` and ``totalPages`` are replaced by the values.
   * - ``generate_tagged_pdf``, ``generate_document_outline``
     - A tagged (accessible) PDF; a document outline.

Of these, the run above checked the paper size, ``landscape`` and ``page_ranges``. The margins, ``scale``, ``prefer_css_page_size``, ``print_background`` and the two generate options are described by the docstring only; their effect on the file was not examined.

What the run shows about the behavior:

- ``page_ranges="2"`` wrote the second page and ``"2-9"`` the second and third (the text of the pages was read back with ``pdftotext``). A page number past the end is cut; a range with no page left (``"9"``) or with its start after its end (``"3-1"``) gives ``ok=False`` and no file.
- ``landscape=True`` with the A4 size gave a 841.92 x 595.92 pt page, and the same three blocks of content filled 6 pages instead of 3.
- A path in a folder that does not exist gives ``ok=False`` and no file.
- The two range errors print one line each on standard error, for example ``PrintToPDF failed with error: Page range exceeds page count`` and ``PrintToPDF failed with error: Page range is invalid (start > end)``. The missing folder prints nothing.
- The docstring of ``print_to_pdf`` says that on Linux you must implement :meth:`~cefweaver.PrintHandler.get_pdf_paper_size`. Here the PDF was written with no print handler at all (above), and a handler that implements ``get_pdf_paper_size`` was never asked in any run of the next section (``get_pdf_paper_size calls: 0``).
- ``print_to_pdf`` was called after the page had finished loading (the ``on_loading`` hook of the view). Calling it earlier was not tried.

Print with a handler (Linux)
----------------------------

:meth:`~cefweaver.BrowserHost.print` starts a print cycle, and so does ``window.print()`` in a page (the docstring of :meth:`~cefweaver.PrintHandler.on_print_start` lists ``print()``, ``window.print()`` and the print button of the PDF extension; only ``print()`` was run here). CEF calls the :class:`~cefweaver.PrintHandler` that :meth:`~cefweaver.Client.get_print_handler` returns:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Call
     - What the application does
   * - ``on_print_start(browser)``
     - Nothing is required.
   * - ``on_print_settings(browser, settings, get_defaults)``
     - With ``get_defaults`` true, fill the :class:`~cefweaver.PrintSettings` with the defaults: device name, DPI, orientation, printable area, copies.
   * - ``on_print_dialog(browser, has_selection, callback)``
     - Show a dialog and call ``callback.continue_(settings)`` or ``callback.cancel()``, and return ``True``; or return ``False`` to cancel at once.
   * - ``on_print_job(browser, document_name, pdf_file_path, callback)``
     - CEF has made the PDF. Copy it or send it to a printer, call ``callback.continue_()`` and return ``True``; return ``False`` to cancel the job.
   * - ``on_print_reset(browser)``
     - The cycle is over.

This script runs the whole cycle without a dialog and without a printer:

.. literalinclude:: recipes/print_handler.py
   :language: python

Without an argument it prints:

.. code-block:: text

   default: start > settings(get_defaults=True) > dialog > job > reset
       pdf (pages, width pt, height pt): (3, 594.96, 841.92)
   landscape: start > settings(get_defaults=True) > dialog > job > reset
       pdf (pages, width pt, height pt): (6, 841.92, 594.96)
   zero-based range (1, 1): start > settings(get_defaults=True) > dialog > job > reset
       pdf (pages, width pt, height pt): (1, 594.96, 841.92)
   print_to_pdf: True get_pdf_paper_size calls: 0

Three conditions must hold for the cycle to reach ``on_print_job``. Each was taken away in turn (the argument of the script):

.. list-table::
   :header-rows: 1
   :widths: 18 42 40

   * - Argument
     - Events
     - Standard error
   * - ``no-handler``
     - None: ``host.print()`` returned and no call came within 5 seconds.
     - Nothing.
   * - ``empty``
     - ``start > settings(get_defaults=True) > reset``: the settings were not filled, so the device name was empty and there was no dialog.
     - ``The selected printer is not available or not installed correctly. Check your printer or try selecting another printer.``
   * - ``no-switch``
     - ``start > settings(get_defaults=True) > dialog > reset``: the dialog was accepted and there was no job.
     - ``print_job_worker_oop.cc:191 Error rendering printed document via service for document 3: kFailed`` and ``Something went wrong when trying to print.  Please check your printer and try again.``
   * - ``instance``
     - None, as with ``no-handler``: ``get_print_handler`` was set on the client object instead of its class.
     - Nothing.

So:

- **A handler is needed.** Without one, ``print()`` does nothing and says nothing.
- **Fill the settings.** CEF does not read the printers of CUPS or anything else; the device name in the settings must be non-empty. The name used above (``demo-printer``) is not a printer, and the cycle still reached ``on_print_job``; sending the PDF to a real printer is left to the application. The text of the error depends on the language of the process (``LANGUAGE``, see :doc:`configuration`).
- **Start CEF with** ``disable-features=EnableOopPrintDrivers`` (``ui.Session(adapter, switches=[("disable-features", "EnableOopPrintDrivers")])`` or :meth:`~cefweaver.CefApp.add_command_line_switch`). Without it the job fails with ``kFailed`` after the dialog (``no-switch`` above). Other values of ``disable-features`` were not tried.
- **The handler must be found on the class.** The views of :mod:`cefweaver.ui` have no print handler. The script gives the view's client a subclass that returns it. Assigning ``get_print_handler`` on the instance had no effect (``instance`` above).
- **The settings reach the PDF.** Besides the printable area, ``set_orientation(True)`` gave a landscape page, and ``set_page_ranges([(1, 1)])`` gave only the second page: the ranges of a :class:`~cefweaver.PrintSettings` are **zero based**, unlike ``page_ranges`` of ``print_to_pdf``. ``set_copies(3)`` left the PDF at 3 pages, so copies go to the printer when the application sends the job. The text of the pages was read back with ``pdftotext``.
- **Cancel and failure look the same.** Returning ``False`` from ``on_print_dialog`` (the script argument ``cancel``) gives ``start > settings(get_defaults=True) > dialog > reset``, the same events as the failure of ``no-switch``. The application knows only that the cycle ended without ``on_print_job``. The failure wrote its reason to standard error; the cancel wrote nothing.
- **The PDF file is deleted after the job.** The file named in ``on_print_job`` existed before and right after ``callback.continue_()`` and was gone 1.5 seconds after the cycle ended. Copy it or send it from inside ``on_print_job``, as the script does.

A complete program with a print dialog drawn in Tk, the printers and papers from CUPS (``pycups``) and ``lp`` to send the PDF is ``examples/print/`` (``printing.py``, ``quickstart.py`` and a ``smoke.py`` that checks it without printing; its README is in Korean). The adapters of :mod:`cefweaver.ui` have no print command of their own: the ``Print`` item of the default menu does nothing (:doc:`limitations`).
