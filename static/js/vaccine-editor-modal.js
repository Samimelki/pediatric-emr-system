/**
 * Vaccine Editor Modal Module
 * Handles modal editing system and field mapping for vaccine updates
 */

// Modal state
let currentEditingVaccine = null;
let currentEditingDose = null;

// Vaccine to database field mapping
function createFieldMapping(vaccine, dose) {
    const fieldMapping = {
        'DTaP - IPV': {
            'd1': 'dtcp1_date',
            'd2': 'dtcp2_date', 
            'd3': 'dtcp3_date',
            'r1': 'dtcp_rappel1_date',
            'r2': 'dtcp_rappel2_date',
            'r3': 'dtcp_rappel3_date',
            'r4': 'dtcp_rappel4_date'
        },
        'Hepatitis B': {
            'd1': 'hep_b1_date',
            'd2': 'hep_b2_date',
            'd3': 'hep_b3_date'
        },
        'Hib (Haemophilus influenzae b)': {
            'd1': 'hib1_date',
            'd2': 'hib2_date', 
            'd3': 'hib3_date',
            'r1': 'hib_rappel_date'
        },
        'MMR (Measles, Mumps, Rubella)': {
            'd1': 'ror_date'
        },
        'Measles (single)': {
            'd1': 'rougeole_seule_date'
        },
        'PPD (TB Skin Test)': {
            'd1': 'monotest1',
            'd2': 'monotest2',
            'd3': 'monotest3'
        }
    };
    
    const vaccineMapping = fieldMapping[vaccine.vaccine_name];
    if (vaccineMapping && vaccineMapping[dose.dose_key]) {
        return {
            field_name: vaccineMapping[dose.dose_key],
            vaccine_name: vaccine.vaccine_name,
            dose_key: dose.dose_key
        };
    }
    
    return { field_name: null };
}

// Function to open modal for timeline vaccines
function openVaccineEditModal(vaccine, dose) {
    const modal = document.getElementById('vaccine-edit-modal');
    const title = document.getElementById('modal-title');
    const dateInput = document.getElementById('vaccine-date-input');
    
    if (!modal || !title || !dateInput) {
        console.error('Modal elements not found');
        return;
    }
    
    // Set modal title
    title.textContent = `Edit ${vaccine.vaccine_name} - ${dose.label}`;
    
    // Pre-fill current date if available
    if (dose.completed_date) {
        dateInput.value = dose.completed_date;
    } else {
        dateInput.value = '';
    }
    
    // Store the vaccine info for saving
    currentEditingVaccine = vaccine;
    currentEditingDose = dose;
    
    modal.style.display = 'block';
    dateInput.focus();
}

// Function to open modal for additional/patient-specific vaccines
function openAdditionalVaccineModal(vaccineName, doseNumber, vaccineId, completedDate, dueDate) {
    const modal = document.getElementById('vaccine-edit-modal');
    const title = document.getElementById('modal-title');
    const dateInput = document.getElementById('vaccine-date-input');
    
    if (!modal || !title || !dateInput) {
        console.error('Modal elements not found');
        return;
    }
    
    // Set modal title
    title.textContent = `Edit ${vaccineName} - Dose ${doseNumber}`;
    
    // Pre-fill current date if available
    if (completedDate && completedDate !== '') {
        dateInput.value = completedDate;
    } else {
        dateInput.value = '';
    }
    
    // Store the vaccine info for saving
    currentEditingVaccine = {
        vaccine_name: vaccineName,
        vaccine_id: vaccineId,
        is_additional: true
    };
    currentEditingDose = {
        label: `Dose ${doseNumber}`,
        dose_number: doseNumber,
        due_date: dueDate
    };
    
    modal.style.display = 'block';
    dateInput.focus();
}

// Function to close modal
function closeVaccineEditModal() {
    const modal = document.getElementById('vaccine-edit-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentEditingVaccine = null;
    currentEditingDose = null;
}

// Function to update vaccine display without page reload (for additional vaccines)
function updateVaccineDisplay(vaccineName, doseNumber, newDate, vaccineId) {
    // Find the vaccine badge that was just updated
    const vaccineItem = Array.from(document.querySelectorAll('.additional-vaccine-item')).find(item => {
        const nameElement = item.querySelector('strong');
        return nameElement && nameElement.textContent.includes(vaccineName);
    });
    
    if (vaccineItem) {
        // Find the specific dose badge
        const doseBadges = vaccineItem.querySelectorAll('.additional-dose-badge');
        const targetBadge = Array.from(doseBadges).find(badge => {
            return badge.textContent.includes(`Dose ${doseNumber}`);
        });
        
        if (targetBadge) {
            // Update the badge to show as completed
            targetBadge.className = 'additional-dose-badge dose-completed';
            targetBadge.innerHTML = `Dose ${doseNumber}<br><small>${newDate}</small>`;
            
            // Update the onclick to reflect the new completed date
            const onclickValue = targetBadge.getAttribute('onclick');
            if (onclickValue) {
                const pattern = new RegExp(`openAdditionalVaccineModal\\('${vaccineName}',\\s*${doseNumber},\\s*'${vaccineId}',\\s*'[^']*',`);
                const replacement = `openAdditionalVaccineModal('${vaccineName}', ${doseNumber}, '${vaccineId}', '${newDate}',`;
                const newOnclick = onclickValue.replace(pattern, replacement);
                targetBadge.setAttribute('onclick', newOnclick);
            }
            
            // Remove pulse animation if present
            targetBadge.classList.remove('pulse-animation');
        }
    }
}

// Initialize modal event handlers
function initializeModalHandlers() {
    // Modal close handlers
    const closeButton = document.querySelector('.modal-close');
    const cancelButton = document.getElementById('modal-cancel');
    const modal = document.getElementById('vaccine-edit-modal');
    
    if (closeButton) {
        closeButton.addEventListener('click', closeVaccineEditModal);
    }
    
    if (cancelButton) {
        cancelButton.addEventListener('click', closeVaccineEditModal);
    }
    
    // Close modal when clicking outside
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeVaccineEditModal();
            }
        });
    }
    
    // Handle Enter key in date input
    const dateInput = document.getElementById('vaccine-date-input');
    if (dateInput) {
        dateInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                if (typeof saveVaccineDate === 'function') {
                    saveVaccineDate();
                }
            }
        });
    }
}

// Export functions for global access
window.VaccineEditor = {
    createFieldMapping,
    openVaccineEditModal,
    openAdditionalVaccineModal,
    closeVaccineEditModal,
    updateVaccineDisplay,
    initializeModalHandlers,
    getCurrentEditingVaccine: () => currentEditingVaccine,
    getCurrentEditingDose: () => currentEditingDose
}; 