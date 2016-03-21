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

function category_selected(hash, category) {
    socket.emit('change_category', {
        data: {
            hash: hash,
            category: category
        }
    });
}

function update_task(task) {
    var stateColor;
    var stateIcon;
    var stateStr;
    var categoryState;
    if (task.cloud_status == 'downloading') {
        stateColor = 'info';
        stateStr = 'Downloading';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'waiting') {
        stateColor = 'warning';
        stateStr = 'Downloading';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'queued') {
        stateColor = 'warning';
        stateStr = 'Download queued';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == null) {
        stateColor = 'success';
        stateStr = 'Finished';
        stateIcon = 'cloud';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'queued') {
        stateColor = 'primary';
        stateStr = 'Download Queue';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'waiting') {
        stateColor = 'info';
        stateStr = 'Waiting on category';
        stateIcon = 'desktop';
        categoryState = '';
        /*
    } else if (task.cloud_status == 'finished' && task.local_status == 'paused') {
        stateColor = 'warning';
        stateStr = 'Download paused';
        stateIcon = 'desktop';
        categoryState = '';
         */
    } else if (task.cloud_status == 'finished' && task.local_status == 'downloading') {
        stateColor = 'primary';
        stateStr = 'Downloading';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'finished') {
        stateColor = 'success';
        stateStr = 'Finished';
        stateIcon = 'desktop';
        categoryState = ' disabled';
    } else if (task.cloud_status == 'finished' && task.local_status == 'stopped') {
        stateColor = 'warning';
        stateStr = 'Download stopped';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'failed: download retrying') {
        stateColor = 'warning';
        stateStr = 'Failed: download retrying soon';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'failed: download') {
        stateColor = 'danger';
        stateStr = 'Failed: download';
        stateIcon = 'desktop';
        categoryState = '';
    } else if (task.cloud_status == 'finished' && task.local_status == 'failed: nzbtomedia') {
        stateColor = 'danger';
        stateStr = 'Failed: nzbtomedia';
        stateIcon = 'desktop';
        categoryState = '';
    } else {
        stateColor = 'danger';
        stateStr = 'check js console';
        console.log('UNKNOWN STATUS - cloud: ' + task.cloud_status + ', local: ' + task.local_status);
    }

    var update = false;
    if ($("#" + task.hash).length > 0) {
        update = true;
    }

    var dropDown = '<div class="dropdown"><button class="btn btn-primary dropdown-toggle' + categoryState + '" type="button" data-toggle="dropdown">' +
        task.category + '<span class="caret"></span></button><ul class="dropdown-menu">';
    for (category in download_categories) {
        dropDown += '<li><a href="javascript:category_selected(\'' + task.hash + '\', \'' + download_categories[category] + '\')" class="download_category">' + download_categories[category] + '</a></li>';
    }
    dropDown += '</ul></div>';

    var htmlString = '<div class="panel panel-default' + (!update ? ' animated fadeInDown' : "") + ' task_panel" id="' + task.hash + '">' +
        '<div class="panel-body">' +
        '<div class="row">' +
        '<span class="col-md-1 text-center">' +
        '<div class="row"><i class="fa fa-' + stateIcon + ' fa-fw fa-2x"></i></div>' +
        '<div class="row"><span class="label label-' + stateColor + '">' + stateStr + '</span></div>' +
        '</span>' +
        '<span class="col-md-1 text-center">' +
        '<div class="row">' + dropDown + '</div>' +
        '</span>' +
        '<span class="col-md-7">' +
        '<div class="row"><h4>' + task.name + '</h4></div>' +
        '<div class="row"><div class="progress"><div class="progress-bar progress-bar-' + stateColor + (task.cloud_status == "downloading" || task.local_status == "downloading" ? " progress-bar-striped active" : "") + '" style="width: ' + task.progress + '%">' + task.progress + '% ' + '</div></div></div>' +
        '<div class="row"><h6>' + (task.progress != 100 ? "Speed: " + task.speed + " ETA: " + task.eta : '') + '</h6></div>' +
        '</span>' +
        '<span class="col-md-3">' +
        '<div class="btn-toolbar text-center"><a class="btn btn-danger delete_btn" href="#" onclick="delete_task(event)"><i class="fa fa-trash-o fa-lg"></i> Delete</a>' + (task.cloud_status == "finished" ? '<a class="btn btn-success" href="https://www.premiumize.me/browsetorrent?hash=' + task.hash + '" target="_blank"><i class="fa fa-folder-open-o fa-lg"></i> Browse</a>' : "") + (task.local_status == "downloading" ? '<a class="btn btn-warning"href="#" onclick="stop_task(event)"><i class="fa fa-trash-o fa-lg"></i> Stop DL</a>' : "") + '</div>' +
        '</span>' +
        '</div>' +
        '</div>' +
        '</div>';

    if (update) {
        $("#" + task.hash).replaceWith(htmlString);
    } else {
        $("#download_section").prepend(htmlString);
    }
}

+function ($) {
    'use strict';
    var originalTorrentPlaceHolder;
    var originalTorrentLabelClass;

    var uploadTorrent = function (torrent) {
        start_loading_upload();
        var data = new FormData();
        data.append('file', torrent);
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

    $('#torrent-file-upload').on('change', function (e) {
        e.preventDefault();
        var files = $(this).prop('files');
        if (files.length > 0) {
            var file = files[0];
            var fileName = file.name;
            var fileExt = '.' + fileName.split('.').pop();
            if (fileExt == '.torrent') {
                uploadTorrent(file);
            } else {
                alert('Nope, not a torrent file...');
            }
        }
        $('#torrent-file-upload[type="file"]').val(null);
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

    $('#torrent-input').on('drop', function (e) {
        e.preventDefault();
        var file = e.originalEvent.dataTransfer.files[0];
        var fileName = file.name;
        var fileExt = '.' + fileName.split('.').pop();
        if (fileExt == '.torrent') {
            uploadTorrent(file);
        } else {
            alert('Nope, not a torrent file...');
        }
        this.placeholder = originalTorrentPlaceHolder;
        this.nextElementSibling.className = originalTorrentLabelClass;
    });

    $('#torrent-input').on('dragenter', function (e) {
        originalTorrentPlaceHolder = this.placeholder;
        var torrentLabel = this.nextElementSibling;
        originalTorrentLabelClass = torrentLabel.className;
        torrentLabel.className = "fa fa-check";
        this.placeholder = 'Drop it!';
        return false;
    });

    $('#torrent-input').on('dragleave', function () {
        this.placeholder = originalTorrentPlaceHolder;
        this.nextElementSibling.className = originalTorrentLabelClass;
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
    socket = io.connect('http://' + document.domain + ':' + location.port);

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

    socket.on('connect', function () {
        socket.emit('hello_server', {
            data: 'Client says hello!'
        });
    });

    socket.on('hello_client', function (msg) {
        console.log(msg.data);
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
    var hash = elem.closest('.panel').attr('id');
    socket.emit('delete_task', {
        data: hash
    });
}
/*
 function pause_task(e) {
 var elem = $(e.target);
 var hash = elem.closest('.panel').attr('id');
 socket.emit('pause_task', {
 data: hash
 });
 }
 */
function stop_task(e) {
    var elem = $(e.target);
    var hash = elem.closest('.panel').attr('id');
    socket.emit('stop_task', {
        data: hash
    });
}

function check_empty() {
    if ($("#download_section").find(".task_panel").length == 0)
        show_no_downloads();
    else
        hide_no_downloads();
}