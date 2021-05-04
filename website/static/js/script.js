document.addEventListener('DOMContentLoaded', ()=>{

    const selects = [document.getElementById('up-course'), 
                    document.getElementById('down-course'), 
                    document.getElementById('del-course')
                    ]

    document.querySelectorAll('.custom-file-input').forEach(fileInput => {
        fileInput.onchange =  ()=>{
            
            document.querySelector(`label[for="${fileInput.id}"]`).innerHTML = fileInput.files[0].name;
        };
    });

    document.querySelector('#add_course_form').onsubmit = ()=> {

        resultAlert("add_course_alert", "Adding course...", "alert-info");
    
        var my_form = document.forms.add_course_form;
        var formData = new FormData(my_form);
        formData.append('api', '0');

        fetch('/add_course', {
            method: 'POST',
            body: formData
        })
        .then((response) => {

            if(response.status == 200) {
                response.json().then((response)=>{

                    selects.forEach(select=>{
                        const option = document.createElement('option');
                        option.value = `${response['course']['course_id']}-${response['course']['batch']}`;
                        option.innerHTML = `${response['course']['course_id']} - ${response['course']['course_name']} (Batch ${response['course']['batch']})`;
                        select.add(option);
                    })
                    
                    resultAlert('add_course_alert', 'Course added!', 'alert-success');
                    
                })
            }

            else {
                response.json().then((response)=>{
                    resultAlert('add_course_alert', response['error'] , 'alert-danger');
                })
            }
        });

        return false;
    };

    document.querySelector('#upload_attendance_form').onsubmit = ()=> {

        resultAlert("upload_attendance_alert", "Updating attendance...", "alert-info");
    
        var my_form = document.forms.upload_attendance_form;
        var formData = new FormData(my_form);

        const identifiers = document.getElementById('up-course').value.split('-');
        formData.append('course_id', identifiers[0]);
        formData.append('batch', identifiers[1]);
        formData.append('api', '0');

        fetch("/upload_attendance", {
            method: 'POST',
            body: formData
        })
        .then((response) => {

            if(response.status == 200) {
                response.json().then((response)=>{                   
                    resultAlert("upload_attendance_alert", "Attendance updated!", "alert-success");
                })
            }

            else {
                response.json().then((response)=>{
                    resultAlert("upload_attendance_alert", response['error'], "alert-danger");
                })
            }
        })
        .catch(error => {
            console.log('Error: ', error);
        });

        return false;
    };

    document.querySelector('#delete_course_form').onsubmit = () => {

        resultAlert('delete_course_alert', 'Deleting course...', 'alert-info');

        var my_form = document.forms.delete_course_form;
        var formData = new FormData(my_form);

        const identifiers = document.getElementById('del-course').value.split('-');
        formData.append('course_id', identifiers[0]);
        formData.append('batch', identifiers[1]);
        formData.append('api', '0');

        fetch('/delete_course', {
            method: 'POST',
            body: formData
        })
        .then((response) => {

            if(response.status == 200) {
                resultAlert('delete_course_alert', 'Deleted course :(', 'alert-success');
                
                const option_value = `${identifiers[0]}-${identifiers[1]}`;
                selects.forEach(select=>{
                    for(var i=0; i<select.length; i++) {
                        if (select.options[i].value == option_value)
                            select.remove(i);
                    }
                });
                
            }

            else {
                response.json().then((response)=>{
                    resultAlert('delete_course_alert', response['error'] , 'alert-danger');
                })
            }
        });
        return false;
    }

    document.querySelector('#gform').addEventListener('click', ()=>{
        document.querySelector('#end-time').disabled = true;
        document.querySelector('#threshold').disabled = true;
        document.querySelector('#end-time').value = '';
        document.querySelector('#threshold').value = '';
    });
    document.querySelector('#teams').addEventListener('click', ()=>{
        document.querySelector('#end-time').disabled = false;
        document.querySelector('#threshold').disabled = false;
    });
});


function refreshAlerts() {
    document.querySelectorAll('.alert').forEach((alert)=>{

        alert.classList.remove('alert-success');
        alert.classList.remove('alert-warning');
        alert.classList.remove('alert-danger');
        alert.classList.remove('alert-info');
        alert.innerHTML = '';
        alert.display = 'none';
    })
}

function resultAlert(alert_id, message, className) {

    refreshAlerts();

    const alert = document.getElementById(alert_id);
    alert.style.display = 'block';
    alert.classList.add(className);
    alert.innerHTML = message;           
}
