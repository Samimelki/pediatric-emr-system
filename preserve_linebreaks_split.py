#!/usr/bin/env python3
"""
Split corrupted patients while preserving exact line break formatting
"""

import xml.etree.ElementTree as ET
import json
import shutil
import re

def preserve_linebreaks_split():
    """Split database while preserving exact line break formatting in dossier cells"""
    
    print("🔄 Starting line-break preserving database split...")
    
    # Step 1: Read the original file as raw text to preserve formatting
    print("📖 Step 1: Reading original file as raw text...")
    source_file = "/Users/samimelki/Documents/Uptodate database cleaned.xml"
    
    with open(source_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Step 2: Parse with ElementTree to identify corrupted patients
    print("📖 Step 2: Identifying currently corrupted patients...")
    current_tree = ET.parse(source_file)
    current_root = current_tree.getroot()
    
    ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
    current_worksheet = current_root.find('.//ss:Worksheet', ns)
    current_table = current_worksheet.find('.//ss:Table', ns)
    current_rows = current_table.findall('.//ss:Row', ns)
    
    # Find header row
    header_row_index = -1
    for i, row in enumerate(current_rows):
        cells = row.findall('.//ss:Cell', ns)
        if cells:
            first_cell_data = cells[0].find('.//ss:Data', ns)
            if first_cell_data is not None and first_cell_data.text and '/fichier/' in first_cell_data.text:
                header_row_index = i
                break
    
    # Identify currently corrupted patients
    currently_corrupted_ids = set()
    
    for i, row in enumerate(current_rows):
        if i <= header_row_index:
            continue
            
        cells = row.findall('.//ss:Cell', ns)
        if not cells:
            continue
        
        patient_id = None
        current_dossier_length = 0
        
        for cell in cells:
            data = cell.find('.//ss:Data', ns)
            if data is not None and data.text:
                if data.text.isdigit():
                    numeric_value = int(data.text)
                    if 900 <= numeric_value <= 15000:
                        patient_id = data.text
                
                if len(data.text) > 1000:
                    current_dossier_length = len(data.text)
        
        if patient_id and current_dossier_length > 9000:
            currently_corrupted_ids.add(patient_id)
    
    print(f"📊 Found {len(currently_corrupted_ids)} currently corrupted patients")
    
    # Step 3: Create backup
    print("📋 Step 3: Creating backup...")
    backup_file = "/Users/samimelki/Documents/backup.xml"
    shutil.copy2(source_file, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    # Step 4: Split using text manipulation to preserve formatting
    print("🔄 Step 4: Splitting files using text manipulation...")
    
    # Split the XML into rows using correct regex pattern
    # The actual format uses <Row> not <ss:Row>
    row_pattern = r'(<Row[^>]*>.*?</Row>)'
    rows = re.findall(row_pattern, original_content, re.DOTALL | re.MULTILINE)
    
    print(f"📊 Found {len(rows)} total rows in XML")
    
    # Find the header row (look for /fichier/ pattern)
    header_row = None
    for row in rows:
        if '/fichier/autres_vac' in row:
            header_row = row
            print("✅ Found header row")
            break
    
    if not header_row:
        print("❌ Could not find header row, trying alternative approach...")
        # Try to find any row with fichier
        for row in rows:
            if '/fichier/' in row:
                header_row = row
                print("✅ Found header row (alternative)")
                break
    
    if not header_row:
        print("❌ Could not find header row at all")
        return
    
    # Classify rows
    corrupted_rows = []
    clean_rows = []
    
    for row in rows:
        if row == header_row:
            continue  # Skip header for now
        
        # Check if this row contains a corrupted patient
        is_corrupted = False
        
        # Extract patient ID from row (look for 4-5 digit numbers)
        patient_id_matches = re.findall(r'<Data[^>]*>(\d{4,5})</Data>', row)
        
        for patient_id in patient_id_matches:
            if patient_id in currently_corrupted_ids:
                # Double-check by looking for long dossier content
                data_blocks = re.findall(r'<Data[^>]*>(.*?)</Data>', row, re.DOTALL)
                for data_block in data_blocks:
                    if len(data_block) > 9000:
                        is_corrupted = True
                        break
                if is_corrupted:
                    break
        
        if is_corrupted:
            corrupted_rows.append(row)
        else:
            clean_rows.append(row)
    
    print(f"📊 Classified {len(corrupted_rows)} corrupted rows and {len(clean_rows)} clean rows")
    
    # Step 5: Create clean database file
    print("🧹 Step 5: Creating clean database...")
    
    # Get the XML structure before and after the table
    table_start = original_content.find('<Table')
    table_end = original_content.find('</Table>') + len('</Table>')
    
    xml_before_table = original_content[:table_start]
    xml_after_table = original_content[table_end:]
    
    # Reconstruct table with only clean rows
    clean_table_content = f'<Table ss:ExpandedColumnCount="55" ss:ExpandedRowCount="{len(clean_rows) + 2}" x:FullColumns="1" x:FullRows="1" ss:DefaultColumnWidth="65" ss:DefaultRowHeight="16">\n'
    
    # Add column definitions (extract from original)
    column_defs_match = re.search(r'(<Column[^>]*/>.*?(?=<Row))', original_content, re.DOTALL)
    if column_defs_match:
        clean_table_content += column_defs_match.group(1)
    
    # Add VFPData row (first row)
    vfpdata_match = re.search(r'(<Row[^>]*>.*?/VFPData.*?</Row>)', original_content, re.DOTALL)
    if vfpdata_match:
        clean_table_content += vfpdata_match.group(1) + '\n'
    
    # Add header row
    clean_table_content += header_row + '\n'
    
    # Add clean rows
    for row in clean_rows:
        clean_table_content += row + '\n'
    clean_table_content += '</Table>'
    
    clean_content = xml_before_table + clean_table_content + xml_after_table
    
    # Write clean database
    clean_file = "clean_patients_only.xml"
    with open(clean_file, 'w', encoding='utf-8') as f:
        f.write(clean_content)
    
    print(f"✅ Clean database created: {clean_file}")
    print(f"   📊 Contains {len(clean_rows)} clean patients")
    
    # Step 6: Create corrupted patients file
    print("🔴 Step 6: Creating corrupted patients file...")
    
    corrupted_table_content = f'<Table ss:ExpandedColumnCount="55" ss:ExpandedRowCount="{len(corrupted_rows) + 2}" x:FullColumns="1" x:FullRows="1" ss:DefaultColumnWidth="65" ss:DefaultRowHeight="16">\n'
    
    # Add column definitions
    if column_defs_match:
        corrupted_table_content += column_defs_match.group(1)
    
    # Add VFPData row
    if vfpdata_match:
        corrupted_table_content += vfpdata_match.group(1) + '\n'
    
    # Add header row
    corrupted_table_content += header_row + '\n'
    
    # Add corrupted rows
    for row in corrupted_rows:
        corrupted_table_content += row + '\n'
    corrupted_table_content += '</Table>'
    
    corrupted_content = xml_before_table + corrupted_table_content + xml_after_table
    
    # Write corrupted patients file
    corrupted_file = "corrupted_patients_only.xml"
    with open(corrupted_file, 'w', encoding='utf-8') as f:
        f.write(corrupted_content)
    
    print(f"✅ Corrupted patients file created: {corrupted_file}")
    print(f"   📊 Contains {len(corrupted_rows)} corrupted patients")
    
    # Step 7: Create original data file (using same text approach)
    print("📋 Step 7: Creating original data file...")
    
    # Read original clean database
    with open("Copy of databasepap.xml", 'r', encoding='utf-8') as f:
        original_clean_content = f.read()
    
    # Extract rows from original clean database
    original_rows = re.findall(row_pattern, original_clean_content, re.DOTALL | re.MULTILINE)
    
    # Find header in original
    original_header_row = None
    for row in original_rows:
        if '/fichier/autres_vac' in row:
            original_header_row = row
            break
    
    if not original_header_row:
        # Fallback
        for row in original_rows:
            if '/fichier/' in row:
                original_header_row = row
                break
    
    # Find rows for corrupted patients in original database
    original_corrupted_rows = []
    
    for row in original_rows:
        if row == original_header_row:
            continue
        
        # Check if this row contains a corrupted patient ID
        patient_id_matches = re.findall(r'<Data[^>]*>(\d{4,5})</Data>', row)
        for patient_id in patient_id_matches:
            if patient_id in currently_corrupted_ids:
                original_corrupted_rows.append(row)
                break
    
    print(f"📊 Found {len(original_corrupted_rows)} original records for corrupted patients")
    
    # Create original data file
    original_table_start = original_clean_content.find('<Table')
    original_table_end = original_clean_content.find('</Table>') + len('</Table>')
    
    original_xml_before_table = original_clean_content[:original_table_start]
    original_xml_after_table = original_clean_content[original_table_end:]
    
    # Get column definitions from original
    original_column_defs_match = re.search(r'(<Column[^>]*/>.*?(?=<Row))', original_clean_content, re.DOTALL)
    original_vfpdata_match = re.search(r'(<Row[^>]*>.*?/VFPData.*?</Row>)', original_clean_content, re.DOTALL)
    
    original_data_table_content = f'<Table ss:ExpandedColumnCount="55" ss:ExpandedRowCount="{len(original_corrupted_rows) + 2}" x:FullColumns="1" x:FullRows="1" ss:DefaultColumnWidth="65" ss:DefaultRowHeight="16">\n'
    
    # Add column definitions
    if original_column_defs_match:
        original_data_table_content += original_column_defs_match.group(1)
    
    # Add VFPData row
    if original_vfpdata_match:
        original_data_table_content += original_vfpdata_match.group(1) + '\n'
    
    # Add header row
    original_data_table_content += original_header_row + '\n'
    
    # Add original corrupted rows
    for row in original_corrupted_rows:
        original_data_table_content += row + '\n'
    original_data_table_content += '</Table>'
    
    original_data_content = original_xml_before_table + original_data_table_content + original_xml_after_table
    
    # Write original data file
    original_data_file = "original_data.xml"
    with open(original_data_file, 'w', encoding='utf-8') as f:
        f.write(original_data_content)
    
    print(f"✅ Original data file created: {original_data_file}")
    print(f"   📊 Contains {len(original_corrupted_rows)} original records")
    
    # Summary
    print(f"\n" + "="*80)
    print(f"📊 LINE-BREAK PRESERVING FILES:")
    print(f"   📁 {backup_file} - Backup of original file")
    print(f"   🧹 {clean_file} - Clean patients only ({len(clean_rows)} patients)")
    print(f"   🔴 {corrupted_file} - Corrupted patients only ({len(corrupted_rows)} patients)")
    print(f"   📋 {original_data_file} - Original data with preserved formatting ({len(original_corrupted_rows)} patients)")
    print(f"\n✅ LINE BREAKS PRESERVED:")
    print(f"   - All dossier cell formatting maintained")
    print(f"   - Date parsing should work correctly")
    print(f"   - Medical record structure intact")
    print(f"\n🔧 WORKFLOW:")
    print(f"   1. Open {original_data_file} and {corrupted_file} in Excel")
    print(f"   2. Copy dossier column (F) from original_data.xml to corrupted_patients_only.xml")
    print(f"   3. Line breaks will be preserved in the copy/paste operation")
    print("="*80)

if __name__ == "__main__":
    preserve_linebreaks_split() 