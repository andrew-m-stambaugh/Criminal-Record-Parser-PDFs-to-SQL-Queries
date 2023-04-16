# Based on https://stackoverflow.com/a/62859169/562769

import sys
from typing import List, Tuple
import re
import fitz  # install with 'pip install pymupdf'

# Pull the pdf 
pdf=sys.argv[1]

# I got the following 3 functions from Stack Overflow and slightly tweaked them.
# I then added comments for viewers to read

def _parse_highlight(annot: fitz.Annot, wordlist: List[Tuple[float, float, float, float, str, int, int, int]]) -> str:
    # Get the vertices of the annotation
    points = annot.vertices
    # Determine how many quads the annotation has
    quad_count = int(len(points) / 4)
    sentences = []
    # For each quad in the annotation
    for i in range(quad_count):
        # Get the rectangle that surrounds the quad
        r = fitz.Quad(points[i * 4 : i * 4 + 4]).rect

        # Get a list of all words that intersect with the rectangle
        words = [w for w in wordlist if fitz.Rect(w[:4]).intersects(r)]
        # Join the words together to form a sentence
        sentences.append(" ".join(w[4] for w in words))
    # Join all of the sentences together to form a complete highlighted section
    sentence = " ".join(sentences)
    return sentence


def handle_page(page):
    # Get a list of all words on the page
    wordlist = page.get_text("words")
    # Sort the words in ascending order first by y-coordinate and then by x-coordinate
    wordlist.sort(key=lambda w: (w[3], w[0]))

    highlights = []
    # Loop through all annotations on the page
    annot = page.firstAnnot
    while annot:
        # If the annotation is a highlight, parse it
        if annot.type[0] == 8:
            highlights.append(_parse_highlight(annot, wordlist))
        annot = annot.next
    return highlights


def main(filepath: str) -> List:
    # Open the PDF document
    doc = fitz.open(filepath)

    highlights = []
    # Loop through all pages in the document
    for page in doc:
        # Handle the page and get any highlights on it
        highlights += handle_page(page)

    return highlights

# Pull out the doc with all of the text from the pdf
doc = fitz.open(pdf)

outputcounter=0
# Loop through each page in the document
for j in range(len(doc)):
    # Set the page and the list of highlighted words
    page = doc[j]
    highlights = []
    highlights += handle_page(page)

    # Separate the different offenses by "Offense Description"
    ofdesc = page.search_for("Offense Description")

    # If it is the second page, there will likely be "Offense Description"
    # twice in the requested information so get rid of the last two
    if j == 1:
        ofdesc = ofdesc[:-2]

    locations = []
    if ofdesc:
        # Find the left edge of the first "Offense Description" occurrence
        leftedge = ofdesc[0][0]
        cutoff = leftedge + 10

        # Find the locations of each "Offense Description"
        for location in ofdesc:
            # Only add the location if it's within the cutoff
            if location[0] < cutoff:
                locations.append(location[1] - 2)

        # Extract the highlighted fields on the page
        fields = []
        for highlight in highlights:
            field = highlight.split(":")[0] + ":"
            fields.append(field)

        # Check for duplicates in fields
        fields = list(set(fields))

        rects = []
        # Extract the rectangles containing the fields of the changes needed to be changed
        for field in fields:
            x = page.search_for(field)
            leftedge = x[0][0]
            cutoff = leftedge + 10
            fieldrects = [rect for rect in x if rect[0] > cutoff]
            rects.extend(fieldrects)

        # Extend right edge to capture the changes themselves
        for rect in rects:
            rect[2] += 100

        # Initializing the list for each offense
        changes = {}
        for j in range(len(locations)):
            changes[j] = []

        # Using the rects of the changes to see which offense they are a part of
        for rect in rects:
            for j in range(len(locations)):
                if rect[1] > locations[j]:
                    if j != (len(locations) - 1):
                        if rect[1] < locations[j + 1]:
                            changes[j].append(rect)
                    else:
                        changes[j].append(rect)

        # Make the changes so they are the text instead of just the rect location.
        for key in changes.keys():
            if changes[key]:
                for i in range(len(changes[key])):
                    changes[key][i] = page.get_textbox(changes[key][i])
        
        # Define the initial SQL update statement
        lines=['UPDATE online_Newlogic.dbo.offenses_iei']
        
        # Set a counter to keep track of the number of fields being updated
        counter2=1
        
        # Loop through each key in the dictionary of changes to be made to the SQL database
        for key in changes.keys():
            
            # Reset the lines and counter for each key
            lines=['UPDATE online_Newlogic.dbo.offenses_iei']
            counter2=1
            
            # Check if there are any changes to be made for this key
            if changes[key]!=[]:
                
                # Loop through each change to be made for this key
                for change in changes[key]:
                    
                    # Define the name of the SQL file to output
                    docname=f'sqloutput{outputcounter}'
                    
                    # Extract the name of the field being updated and the new value
                    field="".join(change.split(":")[0].split())
                    field_change=change.split(":")[1].lstrip()
                    
                    # Change the format of the date field to match the database
                    if len(field_change.split('/'))==3:
                        date=field_change.split('/')
                        month=date[0]
                        day=date[1]
                        year=date[2]
                        field_change=year+month+day
                    
                    # Change the name of certain fields if necessary
                    if field=='CaseNumber':
                        field='Source_CaseNumber'
                    if field=='OffenseDescription':
                        field='OffenseDesc1'
                    if field=='Comment':
                        field='Comment1'
                    
                    # Create the SQL statement to update the field
                    if counter2==1:
                        lines.append('SET '+f"{field} = '{field_change}',")
                    else:
                        lines.append(f"{field} = '{field_change}',")
                    
                    # If the Disposition field is being updated, also update the Disposition_Tagging field
                    if field=='Disposition':
                        lines.append(f"Disposition_Tagging = '',")
                    
                    # Increment the field counter
                    counter2+=1
                
                # Remove the final comma from the SQL statement
                lines[len(lines)-1]=lines[len(lines)-1].split(',')[0]
                
                # Write the SQL statement to a file
                with open(f'{docname}.sql', 'w') as f:
                    for line in lines:
                        f.write(line)
                        f.write('\n')
                
                # Increment the output file counter
                outputcounter+=1


