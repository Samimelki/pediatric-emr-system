/**
 * Vaccine AJAX Handlers Module
 * Handles AJAX save/update functions for vaccine data
 */

// Function to save vaccine date changes
function saveVaccineDate(patientId, onSuccess, onError) {
    const currentEditingVaccine = window.VaccineEditor?.getCurrentEditingVaccine();
    const currentEditingDose = window.VaccineEditor?.getCurrentEditingDose();
    
    if (!currentEditingVaccine || !currentEditingDose) {
        const error = 'No vaccine selected for editing';
        console.error(error);
        if (onError) onError(error);
        else alert(error);
        return;
    }
    
    const dateInput = document.getElementById('vaccine-date-input');
    if (!dateInput) {
        const error = 'Date input not found';
        console.error(error);
        if (onError) onError(error);
        else alert(error);
        return;
    }
    
    const newDate = dateInput.value;
    
    // Validate date format
    if (newDate && !/^\d{4}-\d{2}-\d{2}$/.test(newDate)) {
        const error = 'Please enter date in YYYY-MM-DD format';
        if (onError) onError(error);
        else alert(error);
        return;
    }
    
    // Handle additional vaccines (custom vaccines)
    if (currentEditingVaccine.is_additional) {
        const requestData = {
            vaccine_id: currentEditingVaccine.vaccine_id,
            dose_number: currentEditingDose.dose_number,
            date: newDate
        };
        
        fetch(`/vaccines/patient/${patientId}/additional/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update display without page reload
                if (window.VaccineEditor?.updateVaccineDisplay) {
                    window.VaccineEditor.updateVaccineDisplay(
                        currentEditingVaccine.vaccine_name,
                        currentEditingDose.dose_number,
                        newDate,
                        currentEditingVaccine.vaccine_id
                    );
                }
                
                if (window.VaccineEditor?.closeVaccineEditModal) {
                    window.VaccineEditor.closeVaccineEditModal();
                }
                
                if (onSuccess) onSuccess(data);
            } else {
                const error = 'Error saving vaccine date: ' + (data.error || 'Unknown error');
                console.error(error);
                if (onError) onError(error);
                else alert(error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const errorMsg = 'Error saving vaccine date: ' + error.message;
            if (onError) onError(errorMsg);
            else alert(errorMsg);
        });
    } else {
        // Handle timeline vaccines (existing logic)
        const fieldMapping = window.VaccineEditor?.createFieldMapping(currentEditingVaccine, currentEditingDose);
        
        if (!fieldMapping || !fieldMapping.field_name) {
            const error = 'Unable to determine database field for this vaccine dose';
            console.error(error);
            if (onError) onError(error);
            else alert(error);
            return;
        }
        
        const requestData = {
            field_name: fieldMapping.field_name,
            date: newDate
        };
        
        fetch(`/vaccines/patient/${patientId}/standard/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (window.VaccineEditor?.closeVaccineEditModal) {
                    window.VaccineEditor.closeVaccineEditModal();
                }
                
                if (onSuccess) {
                    onSuccess(data);
                } else {
                    // Reload the page to show updated timeline
                    window.location.reload();
                }
            } else {
                const error = 'Error saving vaccine date: ' + (data.error || 'Unknown error');
                console.error(error);
                if (onError) onError(error);
                else alert(error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const errorMsg = 'Error saving vaccine date: ' + error.message;
            if (onError) onError(errorMsg);
            else alert(errorMsg);
        });
    }
}

// Function to delete a vaccine record
function deleteVaccineRecord(vaccineId, onSuccess, onError) {
    if (!confirm('Are you sure you want to delete this vaccine record?')) {
        return;
    }
    
    fetch(`/vaccines/other/${vaccineId}/delete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (onSuccess) {
                onSuccess(data);
            } else {
                // Remove from DOM or reload page
                window.location.reload();
            }
        } else {
            const error = 'Error deleting vaccine: ' + (data.error || 'Unknown error');
            console.error(error);
            if (onError) onError(error);
            else alert(error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        const errorMsg = 'Error deleting vaccine: ' + error.message;
        if (onError) onError(errorMsg);
        else alert(errorMsg);
    });
}

// Function to add a new vaccine record
function addVaccineRecord(patientId, vaccineData, onSuccess, onError) {
    fetch(`/vaccines/patient/${patientId}/other/add`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(vaccineData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (onSuccess) {
                onSuccess(data);
            } else {
                window.location.reload();
            }
        } else {
            const error = 'Error adding vaccine: ' + (data.error || 'Unknown error');
            console.error(error);
            if (onError) onError(error);
            else alert(error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        const errorMsg = 'Error adding vaccine: ' + error.message;
        if (onError) onError(errorMsg);
        else alert(errorMsg);
    });
}

// Initialize save button handler
function initializeSaveHandler(patientId, onSuccess, onError) {
    const saveButton = document.getElementById('modal-save');
    if (saveButton) {
        // Remove any existing listeners
        const newSaveButton = saveButton.cloneNode(true);
        saveButton.parentNode.replaceChild(newSaveButton, saveButton);
        
        // Add new listener
        newSaveButton.addEventListener('click', () => {
            saveVaccineDate(patientId, onSuccess, onError);
        });
    }
}

// Export functions for global access
window.VaccineAjax = {
    saveVaccineDate,
    deleteVaccineRecord,
    addVaccineRecord,
    initializeSaveHandler
}; 