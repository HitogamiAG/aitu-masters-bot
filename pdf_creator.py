from aiogram.types import InputFile
from io import BytesIO
from fpdf import FPDF
from datetime import datetime

pdf_w=210
pdf_h=297
logo = 'imgs/logo.png'

global title
title = 'AITU Masters'

class PDF(FPDF):
    def header(self):
        self.image('imgs/logo.png', x = self.w - 30, y = 15, w = 30, h=30)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Text color in gray
        self.set_text_color(128)
        # Page number
        self.cell(0, 10, 'Page ' + str(self.page_no()), 0, 0, 'C')
    
    def chapter_title(self, num, label):
        # Arial 12
        self.set_font('Arial', '', 12)
        # Background color
        self.set_fill_color(200, 220, 255)
        # Title
        self.cell(0, 6, 'Chapter %d : %s' % (num, label), 0, 1, 'L', 1)
        # Line break
        self.ln(4)

    def chapter_body(self, txt):
        # Times 12
        self.set_font('Times', '', 12)
        # Output justified text
        self.multi_cell(0, 5, txt)
        # Line break
        self.ln()
        # Mention in italics
        self.set_font('', 'I')

    def print_chapter(self, num, title, txt):
        self.add_page()
        self.chapter_title(num, title)
        self.chapter_body(txt)
    


def generate_pdf(scholar_list):
    pdf = PDF()
    pdf.set_title(title)
    pdf.set_author('Jules Verne')

    for number, (short_info, full_info) in enumerate(scholar_list):
        pdf.print_chapter(number+1, short_info.title,
f""" 
ID: {short_info.scholarship_id}

Title:
{short_info.title}

University:
{short_info.university_title}

Link:
{short_info.link}

Deadline: {short_info.deadline} 

Country: {short_info.country}

Comment: {short_info.comment} 

Rating: {short_info.rating} 

Description:
{full_info.description} 

Field of Study:
{full_info.field} 

Amount of scholarships: {full_info.scholarship_amount} 

Scholarship value:
{full_info.scholarship_value} 

Audithory:
{full_info.audithory} 
""")

    pdf_file = BytesIO(pdf.output("pdf.pdf", "S").encode('latin-1'))
    return InputFile(pdf_file, f"wishlist_{str(datetime.now())[:-10].replace(' ', '-').replace(':', '-')}.pdf")

if __name__ == '__main__':
    None