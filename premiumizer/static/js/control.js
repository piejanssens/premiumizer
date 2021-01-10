var socket;
var loaded_tasks = false;
var download_categories = [];

function start_loading_upload() {
    $("#loading_upload").attr('style', 'display: inline');
}

function stop_loading_upload() {
    $("#loading_upload").attr('style', 'display: none');
    $('#magnet-input').val('');
}

function stop_loading_download_tasks() {
    $("#loading_download_tasks").attr('style', 'display: none');
}

function show_no_downloads() {
    $("#no_downloads").attr('style', 'display: inline');
}

function hide_no_downloads() {
    $("#no_downloads").attr('style', 'display: none');
}

function show_premiumize_connect_error() {
    $('#premiumize_connect_error').attr('style', 'display: inline');
    $('#main_container').attr('style', 'display: none');
}

function category_selected(id, category) {
    socket.emit('change_category', {
        data: {
            id: id,
            category: category
        }
    });
}

function update_task(task) {
    var stateColor;
    var stateIcon;
    var stateStr;
    var categoryState;
    if (task.cloud_status == 'running') {
        stateColor = 'info';
        stateStr = 'Downloading';
        stateIcon = 'cloud-download';
        categoryState = '';
    } else if (task.cloud_status == 'waiting') {
        stateColor = 'warning';
        stateStr = 'Downloading';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'queued') {
        stateColor = 'warning';
        stateStr = 'Download queued';
        stateIcon = 'cloud-upload';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == null) {
        stateColor = 'success';
        stateStr = 'Finished';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'seeding' && task.local_status == null) {
        stateColor = 'success';
        stateStr = 'Seeding';
        stateIcon = 'cloud';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'queued') {
        stateColor = 'primary';
        stateStr = 'Download Queue';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'waiting') {
        stateColor = 'info';
        stateStr = 'Waiting on category';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'seeding' && task.local_status == 'waiting') {
        stateColor = 'info';
        stateStr = 'Waiting on category / Seeding';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'download_disabled') {
        stateColor = 'info';
        stateStr = 'Downloads are disabled';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'paused') {
        stateColor = 'warning';
        stateStr = 'Download paused';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'downloading') {
        stateColor = 'primary';
        stateStr = 'Downloading';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'finished') {
        stateColor = 'success';
        stateStr = 'Finished';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'finished_waiting') {
        stateColor = 'success';
        stateStr = 'Waiting to delete';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'finished_seeding') {
        stateColor = 'success';
        stateStr = 'Waiting to delete / Seeding';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'stopped') {
        stateColor = 'warning';
        stateStr = 'Download stopped';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'failed: download retrying') {
        stateColor = 'warning';
        stateStr = 'Failed: download retrying soon';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'failed: download') {
        stateColor = 'danger';
        stateStr = 'Failed: download';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'failed: nzbToMedia') {
        stateColor = 'danger';
        stateStr = 'Failed: nzbToMedia';
        stateIcon = 'desktop';
        categoryState = '';
    } else if ((task.cloud_status == 'finished' || task.cloud_status == 'seeding') && task.local_status == 'failed: Filehost') {
        stateColor = 'danger';
        stateStr = 'Failed: Filehost';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'error') {
        stateColor = 'danger';
        stateStr = 'Cloud: Error';
        stateIcon = 'cloud-download';
        categoryState = '';
    } else {
        stateColor = 'danger';
        stateStr = 'check js console';
        stateIcon = 'exclamation-triangle';
        console.log('UNKNOWN STATUS - cloud: ' + task.cloud_status + ', local: ' + task.local_status);
    }

    var update = false;
    if ($("#" + task.id).length > 0) {
        update = true;
    }

    var dropDown = '<div class="dropdown"><button class="btn btn-xs btn-primary dropdown-toggle' + categoryState + '" type="button" data-toggle="dropdown">' +
        (task.category ? task.category : 'Category ') + '<span class="caret"></span></button><ul class="dropdown-menu">';
    for (category in download_categories) {
        dropDown += '<li><a href="javascript:category_selected(\'' + task.id + '\', \'' + download_categories[category] + '\')" class="download_category">' + download_categories[category] + '</a></li>';
    }
    dropDown += '</ul></div>';

    var htmlString = '<div class="panel panel-default' + (!update ? ' animated fadeInDown' : "") + ' task_panel" id="' + task.id + '">' +
        '<div class="panel-heading clearfix"><h3 class="panel-title pull-left" style="padding-top: 7.5px;" title="' + task.name + '">' + task.name.substring(0, 100) + '</h3>' +
        '<div class="btn-toolbar pull-right">' +
        '<a class="btn btn-xs btn-danger delete_btn pointer" onclick="delete_task(event)"><i class="fa fa-trash-o fa-lg"></i></a>'
        + (task.cloud_status == "finished" ? (!task.file_id ? '<a class="btn btn-xs btn-success" href="https://www.premiumize.me/files?folder_id=' + task.folder_id + '" target="_blank"><i class="fa fa-folder-open-o fa-lg"></i></a>' : "")
            + (task.file_id ? '<a class="btn btn-xs btn-success" href="https://www.premiumize.me/files?file_id=' + task.file_id + '" target="_blank"><i class="fa fa-folder-open-o fa-lg"></i></a>' : "") : "")
        + (task.local_status == "downloading" || (task.local_status == 'paused') ? '<a class="btn btn-xs btn-warning pointer" onclick="stop_task(event)"><i class="fa fa-stop fa-lg"></i></a>' : "")
        + (task.local_status == "downloading" ? '<a class="btn btn-xs btn-warning pointer" onclick="pause_resume_task(event)"><i class="fa fa-pause fa-lg"></i></a>' : "")
        + (task.local_status == "paused" ? '<a class="btn btn-xs btn-warning pointer" onclick="pause_resume_task(event)"><i class="fa fa-play fa-lg"></i></a>' : "") +
        '</div>' +
        '</div>' +
        '<div class="panel-body">' +
        '<div class="row">' +
        '<span class="col-md-2 text-center"><div class="col-md-12">' +
        '<div class="row"><i class="fa fa-' + stateIcon + ' fa-fw fa-2x"></i></div>' +
        '<div class="row"><span class="label label-' + stateColor + '">' + stateStr + '</span></div>' +
        '<div class="row"><h5>' + task.type + '</h5></div></div>' +
        '</span>' +
        '<span class="col-md-8"><div class="col-md-12">' +
        '<div class="row"><h6>' + (task.progress != 100 ? "Speed: " + task.speed + "Size: " + task.dlsize + " ETA: " + task.eta : 'Inactive') + '</h6></div>' +
        '<div class="row"><div class="progress"><div class="progress-bar progress-bar-' + stateColor + (task.cloud_status == "downloading" || task.local_status == "downloading" ? " progress-bar-striped active" : "") + '" style="width: ' + task.progress + '%">' + task.progress + '% ' + '</div></div></div></div>' +
        '</span>' +
        '<span class="col-md-2"><div class="col-md-12">' +
        '<div class="row"><h6>&nbsp;</h6></div>' +
        '<div class="row">' + dropDown + '</div></div>' +
        '</span>' +
        '</div>' +
        '</div>' +
        '</div>';

    if (update) {
        $("#" + task.id).replaceWith(htmlString);
    } else {
        $("#download_section").prepend(htmlString);
    }
}


+function ($) {
    'use strict';
    var originalFilePlaceHolder;
    var originalFileLabelClass;

    var uploadFile = function (file) {
        start_loading_upload();
        var data = new FormData();
        data.append('file', file);
        $.ajax({
            type: "POST",
            url: 'upload',
            data: data,
            processData: false,
            contentType: false,
            cache: false,
            success: function (data, textStatus, jqXHR) {
                //data - response from server
                console.log('done');
                stop_loading_upload();
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log(errorThrown);
                stop_loading_upload();
            }
        });
    };

    var uploadMagnet = function (magnet) {
        console.log(magnet);
        $.ajax({
            type: "POST",
            url: 'upload',
            data: magnet,
            contentType: 'text/plain',
            success: function (data, textStatus, jqXHR) {
                //data - response from server
                console.log('done');
                $('#magnet-input').val('');
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log(errorThrown);
                $('#magnet-input').val('');
            }
        });
    };

    var uploadFilehostUrls = function (filehosturls) {
        console.log(filehosturls);
        $.ajax({
            type: "POST",
            url: 'upload',
            data: filehosturls,
            contentType: 'text/plain',
            success: function (data, textStatus, jqXHR) {
                //data - response from server
                console.log('done');
                $('#filehost_urls').val('');
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log(errorThrown);
                $('#filehost_urls').val('');
            }
        });
    };

    $('#filehost_urls').on('click', function () {
        var element = document.getElementsByClassName("form-control custom-control");
        setTimeout(function () {
            var urls = $(element).val();
            uploadFilehostUrls(urls);
        }, 100);
    });

    $('#file-file-upload').on('change', function (e) {
        e.preventDefault();
        var files = $(this).prop('files');
        if (files.length > 0) {
            var file = files[0];
            var fileName = file.name;
            var fileExt = '.' + fileName.split('.').pop();
            if (fileExt == '.torrent' || fileExt == '.nzb' || fileExt == '.magnet') {
                uploadFile(file);
            } else {
                alert('Nope, not a valid file...');
            }
        }
        $('#file-file-upload[type="file"]').val(null);
    });

    $('#magnet-input').on('paste', function (e) {
        var element = this;
        setTimeout(function () {
            var magnet = $(element).val();
            if (magnet.match(/magnet:\?xt=urn:btih:[a-z0-9]{20,50}.+/i) != null) {
                uploadMagnet(magnet);
            } else {
                alert('Nope, not a valid magnet...');
            }
        }, 100);
    });

    $('#magnet-input').on('drop', function (e) {
        e.preventDefault();
        var magnet = e.originalEvent.dataTransfer.getData('Text');
        setTimeout(function () {
            if (magnet.match(/magnet:\?xt=urn:btih:[a-z0-9]{20,50}.+/i) != null) {
                uploadMagnet(magnet);
            } else {
                alert('Nope, not a valid magnet...');
            }
        }, 100);
        this.placeholder = originalFilePlaceHolder;
        this.nextElementSibling.className = originalFileLabelClass;
    });

    $('#magnet-input').on('dragenter', function (e) {
        originalFilePlaceHolder = this.placeholder;
        var fileLabel = this.nextElementSibling;
        originalFileLabelClass = fileLabel.className;
        fileLabel.className = "fa fa-check";
        this.placeholder = 'Drop it!';
        return false;
    });

    $('#magnet-input').on('dragleave', function () {
        this.placeholder = originalFilePlaceHolder;
        this.nextElementSibling.className = originalFileLabelClass;
        return false;
    });

    $('#file-input').on('drop', function (e) {
        e.preventDefault();
        var file = e.originalEvent.dataTransfer.files[0];
        var fileName = file.name;
        var fileExt = '.' + fileName.split('.').pop();
        if (fileExt == '.torrent' || fileExt == '.nzb' || fileExt == '.magnet') {
            uploadFile(file);
        } else {
            alert('Nope, not a valid file...');
        }
        this.placeholder = originalFilePlaceHolder;
        this.nextElementSibling.className = originalFileLabelClass;
    });

    $('#file-input').on('dragenter', function (e) {
        originalFilePlaceHolder = this.placeholder;
        var fileLabel = this.nextElementSibling;
        originalFileLabelClass = fileLabel.className;
        fileLabel.className = "fa fa-check";
        this.placeholder = 'Drop it!';
        return false;
    });

    $('#file-input').on('dragleave', function () {
        this.placeholder = originalFilePlaceHolder;
        this.nextElementSibling.className = originalFileLabelClass;
        return false;
    });

    // Disable default drop behavior in body
    $(document.body).bind("dragover", function (e) {
        e.preventDefault();
        return false;
    });

    $(document.body).bind("drop", function (e) {
        e.preventDefault();
        return false;
    });

    // start up the SocketIO connection to the server
    socket = io.connect('//' + document.domain + ':' + location.port, {
                        'path': window.location.pathname + 'socket.io'
    });
    socket.on('download_categories', function (msg) {
        download_categories = msg.data;
    });

    socket.on('tasks_updated', function (msg) {
        if (!loaded_tasks) {
            loaded_tasks = true;
            stop_loading_download_tasks();
        }
        check_empty();
    });

    socket.on('update_task', function (msg) {
        console.log(msg.task);
        update_task(msg.task);
    });

    socket.on('delete_failed', function (msg) {
        console.log('Delete failed: ' + msg.data);
    });

    socket.on('premiumize_connect_error', function (msg) {
        show_premiumize_connect_error();
    });

    socket.on('delete_success', function (msg) {
        console.log('Delete success: ' + msg.data);
        $("#" + msg.data).addClass('animated fadeOutRightBig');
        $("#" + msg.data).one('webkitAnimationEnd mozAnimationEnd MSAnimationEnd oanimationend animationend', function () {
            $("#" + msg.data).remove();
        });
        check_empty();
    });

}(jQuery);

function delete_task(e) {
    var elem = $(e.target);
    var id = elem.closest('.panel').attr('id');
    socket.emit('delete_task', {
        data: id
    });
}

function delete_all_failed_tasks() {
    var confirmationResult = confirm('Are you sure, you want to delete all failed tasks?')
    if(confirmationResult == true)
    {
        socket.emit('delete_all_failed_tasks');
    }
}

function pause_resume_task(e) {
    var elem = $(e.target);
    var id = elem.closest('.panel').attr('id');
    socket.emit('pause_resume_task', {
        data: id
    });
}

function stop_task(e) {
    var elem = $(e.target);
    var id = elem.closest('.panel').attr('id');
    socket.emit('stop_task', {
        data: id
    });
}

function check_empty() {
    if ($("#download_section").find(".task_panel").length == 0)
        show_no_downloads();
    else
        hide_no_downloads();
}
