/**
 * Vaccine Timeline Core Module
 * Handles timeline visualization, age range management, and positioning logic
 */

// Timeline state
let vaccineLabels = [];
let currentAgeRange = '0-1';

// Function to get abbreviated vaccine name
function getVaccineAbbreviation(vaccineName) {
    const abbreviations = {
        'DTaP - IPV': 'DTaP',
        'Hepatitis A': 'HepA',
        'Hepatitis B': 'HepB',
        'Hib (Haemophilus influenzae b)': 'Hib',
        'MMR (Measles, Mumps, Rubella)': 'MMR',
        'Pneumococcal PCV': 'PCV',
        'Rotavirus': 'RV',
        'Varicella': 'VZV',
        'Influenza': 'Flu',
        'Meningococcal ACWY': 'MenA',
        'PPD (TB Skin Test)': 'PPD',
        'Covid 19': 'COV',
        'HPV': 'HPV'
    };
    
    // Look for exact match first
    if (abbreviations[vaccineName]) {
        return abbreviations[vaccineName];
    }
    
    // Look for partial matches
    for (const [full, abbrev] of Object.entries(abbreviations)) {
        if (vaccineName.includes(full) || full.includes(vaccineName)) {
            return abbrev;
        }
    }
    
    // Fallback: create abbreviation from first letters of significant words
    return vaccineName
        .split(/[\s\-\(\)]+/)
        .filter(word => word.length > 2 && !['and', 'the', 'of', 'or'].includes(word.toLowerCase()))
        .map(word => word.charAt(0).toUpperCase())
        .join('')
        .substring(0, 4);
}

// Function to get age range configuration
function getAgeRangeConfig(range) {
    switch(range) {
        case '0-1':
            return {
                minMonths: 0,
                maxMonths: 12,
                labels: [
                    { months: 0, label: 'Birth' },
                    { months: 2, label: '2M' },
                    { months: 4, label: '4M' },
                    { months: 6, label: '6M' },
                    { months: 9, label: '9M' },
                    { months: 12, label: '1Y' }
                ]
            };
        case '1-2':
            return {
                minMonths: 12,
                maxMonths: 24,
                labels: [
                    { months: 12, label: '1Y' },
                    { months: 15, label: '15M' },
                    { months: 18, label: '18M' },
                    { months: 21, label: '21M' },
                    { months: 24, label: '2Y' }
                ]
            };
        case '2-10':
            return {
                minMonths: 24,
                maxMonths: 120,
                labels: [
                    { months: 24, label: '2Y' },
                    { months: 36, label: '3Y' },
                    { months: 48, label: '4Y' },
                    { months: 60, label: '5Y' },
                    { months: 72, label: '6Y' },
                    { months: 84, label: '7Y' },
                    { months: 96, label: '8Y' },
                    { months: 108, label: '9Y' },
                    { months: 120, label: '10Y' }
                ]
            };
        case '10-18':
            return {
                minMonths: 120,
                maxMonths: 216,
                labels: [
                    { months: 120, label: '10Y' },
                    { months: 132, label: '11Y' },
                    { months: 144, label: '12Y' },
                    { months: 156, label: '13Y' },
                    { months: 168, label: '14Y' },
                    { months: 180, label: '15Y' },
                    { months: 192, label: '16Y' },
                    { months: 204, label: '17Y' },
                    { months: 216, label: '18Y' }
                ]
            };
        case 'all':
        default:
            return {
                minMonths: 0,
                maxMonths: 300, // Extended to 25 years to accommodate far-future vaccines
                labels: [
                    { months: 0, label: 'Birth' },
                    { months: 24, label: '2Y' },
                    { months: 48, label: '4Y' },
                    { months: 72, label: '6Y' },
                    { months: 96, label: '8Y' },
                    { months: 120, label: '10Y' },
                    { months: 144, label: '12Y' },
                    { months: 168, label: '14Y' },
                    { months: 192, label: '16Y' },
                    { months: 216, label: '18Y' },
                    { months: 240, label: '20Y' },
                    { months: 264, label: '22Y' },
                    { months: 288, label: '24Y' }
                ]
            };
    }
}

// Function to update timeline labels with overlap prevention
function updateTimelineLabels(range) {
    const labelsContainer = document.getElementById('timeline-labels');
    if (!labelsContainer) return;
    
    labelsContainer.innerHTML = '';
    const config = getAgeRangeConfig(range);
    const rangeSpan = config.maxMonths - config.minMonths;
    
    // Calculate positions and filter out overlapping labels
    const labelPositions = [];
    const minSpacing = 8; // Minimum percentage spacing between labels
    
    config.labels.forEach(labelData => {
        const position = ((labelData.months - config.minMonths) / rangeSpan) * 100;
        
        // Check if this position would overlap with existing labels
        const hasOverlap = labelPositions.some(existingPos => 
            Math.abs(position - existingPos) < minSpacing
        );
        
        if (!hasOverlap) {
            labelPositions.push(position);
            
            const labelDiv = document.createElement('div');
            labelDiv.className = 'age-label';
            labelDiv.style.left = `${position}%`;
            labelDiv.textContent = labelData.label;
            labelsContainer.appendChild(labelDiv);
        }
    });
}

// Function to update current age marker
function updateCurrentAgeMarker(range, patientBirthDate) {
    if (!patientBirthDate) return;
    
    const birthDate = new Date(patientBirthDate);
    const today = new Date();
    const currentAgeMonths = (today.getFullYear() - birthDate.getFullYear()) * 12 + (today.getMonth() - birthDate.getMonth());
    
    const config = getAgeRangeConfig(range);
    const currentAgeMarker = document.querySelector('.current-age-marker');
    
    if (!currentAgeMarker) return;
    
    if (currentAgeMonths >= config.minMonths && currentAgeMonths <= config.maxMonths) {
        const position = ((currentAgeMonths - config.minMonths) / (config.maxMonths - config.minMonths)) * 100;
        currentAgeMarker.style.left = `${position}%`;
        currentAgeMarker.style.display = 'block';
    } else {
        currentAgeMarker.style.display = 'none';
    }
}

// Function to create vaccine labels for current range with smart positioning
function createVaccineLabels(range, timelineData) {
    const timelineContainer = document.querySelector('.timeline-container');
    if (!timelineContainer || !timelineData) return;
    
    // Clear existing labels
    vaccineLabels.forEach(labelData => {
        if (labelData.element && labelData.element.parentNode) {
            labelData.element.parentNode.removeChild(labelData.element);
        }
    });
    vaccineLabels = [];
    
    const config = getAgeRangeConfig(range);
    const rangeSpan = config.maxMonths - config.minMonths;
    
    // Collect all doses in current range
    const dosesInRange = [];
    
    timelineData.forEach(vaccine => {
        if (vaccine.doses) {
            vaccine.doses.forEach(dose => {
                if (dose.age_months >= config.minMonths && dose.age_months <= config.maxMonths) {
                    dosesInRange.push({
                        vaccine: vaccine,
                        dose: dose,
                        position: ((dose.age_months - config.minMonths) / rangeSpan) * 100
                    });
                }
            });
        }
    });
    
    // Sort by position
    dosesInRange.sort((a, b) => a.position - b.position);
    
    // Create labels with smart positioning to avoid overlaps
    const usedPositions = [];
    const minSpacing = 12; // Minimum spacing between labels in percentage
    
    dosesInRange.forEach(item => {
        let finalPosition = item.position;
        
        // Check for overlaps and adjust position
        let attempts = 0;
        while (attempts < 10) {
            const hasOverlap = usedPositions.some(pos => 
                Math.abs(finalPosition - pos) < minSpacing
            );
            
            if (!hasOverlap) {
                break;
            }
            
            // Try shifting up or down
            finalPosition = item.position + (attempts % 2 === 0 ? attempts * 2 : -attempts * 2);
            attempts++;
        }
        
        // Ensure position stays within bounds
        finalPosition = Math.max(2, Math.min(98, finalPosition));
        usedPositions.push(finalPosition);
        
        // Create label element
        const labelElement = document.createElement('div');
        labelElement.className = `vaccine-label dose-${item.dose.status.toLowerCase()}`;
        labelElement.style.left = `${finalPosition}%`;
        labelElement.innerHTML = `
            <div class="vaccine-name">${getVaccineAbbreviation(item.vaccine.vaccine_name)}</div>
            <div class="dose-info">${item.dose.label}</div>
        `;
        
        // Make it clickable if editable
        if (item.dose.is_editable !== false) {
            labelElement.style.cursor = 'pointer';
            labelElement.addEventListener('click', () => {
                if (typeof openVaccineEditModal === 'function') {
                    openVaccineEditModal(item.vaccine, item.dose);
                }
            });
        }
        
        timelineContainer.appendChild(labelElement);
        
        vaccineLabels.push({
            element: labelElement,
            vaccine: item.vaccine,
            dose: item.dose
        });
    });
}

// Initialize age range buttons
function initializeAgeRangeButtons(timelineData, patientBirthDate) {
    document.querySelectorAll('.age-range-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const range = this.dataset.range;
            currentAgeRange = range;
            
            // Update active button
            document.querySelectorAll('.age-range-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Update timeline
            updateTimelineLabels(range);
            updateCurrentAgeMarker(range, patientBirthDate);
            createVaccineLabels(range, timelineData);
        });
    });
}

// Export functions for global access
window.VaccineTimeline = {
    getVaccineAbbreviation,
    getAgeRangeConfig,
    updateTimelineLabels,
    updateCurrentAgeMarker,
    createVaccineLabels,
    initializeAgeRangeButtons,
    getCurrentRange: () => currentAgeRange,
    setCurrentRange: (range) => { currentAgeRange = range; }
}; 