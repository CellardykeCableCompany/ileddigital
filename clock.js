/*
  A small flip clock: hours, minutes and seconds in the visitor's own time.
  Adapted from the clock on wemakeanything.net.

  This is the site's only script. It makes no connections to anything
  outside the site, and stores nothing. If it doesn't run, the page is
  exactly the same, just without a clock. To remove the clock, delete
  this file and the two lines in index.html that mention it.
*/
(function () {
  var board = document.querySelector('.clock');
  if (!board) return;

  // One flip digit: two fixed halves, plus two flaps that animate.
  function Digit() {
    var el = document.createElement('div');
    el.className = 'tile';
    el.innerHTML =
      '<div class="half top"><span class="num">0</span></div>' +
      '<div class="half bot"><span class="num">0</span></div>' +
      '<div class="flap fold"><span class="num">0</span><div class="shade"></div></div>' +
      '<div class="flap unfold"><span class="num">0</span><div class="shade"></div></div>' +
      '<i class="pin l"></i><i class="pin r"></i>';
    this.el = el;
    this.topN = el.querySelector('.top .num');
    this.botN = el.querySelector('.bot .num');
    this.fold = el.querySelector('.fold');
    this.foldN = this.fold.querySelector('.num');
    this.unfold = el.querySelector('.unfold');
    this.unfoldN = this.unfold.querySelector('.num');
    this.cur = null;
  }

  Digit.prototype.set = function (v) {
    v = String(v);
    if (v === this.cur) return;
    var old = this.cur;
    this.cur = v;
    if (old === null) {                 // first time: no flip, just show it
      this.topN.textContent = v; this.botN.textContent = v;
      this.foldN.textContent = v; this.unfoldN.textContent = v;
      return;
    }
    this.topN.textContent = v;          // revealed once the top flap folds away
    this.botN.textContent = old;        // stays old until the new flap lands
    this.foldN.textContent = old;
    this.unfoldN.textContent = v;
    this.fold.classList.remove('run');
    this.unfold.classList.remove('run');
    void this.el.offsetWidth;           // restart the animation
    this.fold.classList.add('run');
    this.unfold.classList.add('run');
    var self = this;
    var done = function () {
      self.botN.textContent = v;
      self.unfold.removeEventListener('animationend', done);
    };
    this.unfold.addEventListener('animationend', done);
  };

  // Three pairs of digits: hours, minutes, seconds.
  var pairs = [];
  for (var g = 0; g < 3; g++) {
    var pair = document.createElement('div');
    pair.className = 'pair';
    var digits = [new Digit(), new Digit()];
    pair.appendChild(digits[0].el);
    pair.appendChild(digits[1].el);
    board.appendChild(pair);
    pairs.push(digits);
  }

  function show(i, n) {
    var s = (n < 10 ? '0' : '') + n;
    pairs[i][0].set(s[0]);
    pairs[i][1].set(s[1]);
  }

  function tick() {
    var now = new Date();
    show(0, now.getHours());
    show(1, now.getMinutes());
    show(2, now.getSeconds());
  }

  // Start now, then tick exactly on each new second.
  tick();
  setTimeout(function () {
    tick();
    setInterval(tick, 1000);
  }, 1000 - (Date.now() % 1000));
})();
