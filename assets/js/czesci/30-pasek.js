// Pasek „Zadzwoń” na telefonie pokazuje się dopiero, gdy na ekranie nie ma tych samych akcji: przycisków w hero
// ani stopki z kontaktem ([data-ukryj-pasek]) — ten sam telefon nie jest widoczny dwa razy.
// Schowany pasek jest „inert” (fokus klawiatury go omija). Bez JS pasek jest widoczny zawsze.
(() => {
  const pasek = document.querySelector('.callbar');
  if (!pasek) return;
  const ustaw = (widoczny) => {
    pasek.classList.toggle('is-widoczny', widoczny);
    pasek.inert = !widoczny;
  };
  const cele = document.querySelectorAll('[data-ukryj-pasek]');
  if (!cele.length || !('IntersectionObserver' in window)) { ustaw(true); return; }
  const widoczne = new Set();
  const obserwator = new IntersectionObserver((wpisy) => {
    wpisy.forEach((w) => (w.isIntersecting ? widoczne.add(w.target) : widoczne.delete(w.target)));
    ustaw(widoczne.size === 0);
  });
  cele.forEach((c) => obserwator.observe(c));
})();
