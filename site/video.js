/* video.js: plays a YouTube video in place on request (why/index.html). The page ships a plain
   link to the video, which works without JavaScript. This script turns each link into a play
   button, and only when it is pressed swaps in a youtube-nocookie player, so nothing loads from
   YouTube before the reader asks for it. Focus moves to the player that replaces the button. */
(function () {
  'use strict';

  Array.prototype.forEach.call(document.querySelectorAll('a.video-poster[data-video]'), function (link) {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = link.className;
    while (link.firstChild) button.appendChild(link.firstChild);
    var verb = button.querySelector('.video-verb');
    var where = button.querySelector('.video-where');
    if (verb) verb.textContent = 'Play ';
    if (where) where.textContent = '';

    button.addEventListener('click', function () {
      var frame = document.createElement('iframe');
      frame.className = 'video-frame';
      frame.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(link.dataset.video) + '?autoplay=1';
      frame.title = link.dataset.title;
      frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      frame.allowFullscreen = true;
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      button.replaceWith(frame);
      frame.focus();
    });

    link.replaceWith(button);
  });
})();
