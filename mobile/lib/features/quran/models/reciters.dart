/// Quran reciters available for the listen feature.
///
/// `id` is the everyayah.com data folder; the per-ayah URL is
/// `https://everyayah.com/data/<id>/<surah:03d><ayah:03d>.mp3`.
/// All folders verified to serve ayah 1..last (2026-06-15).
class Reciter {
  final String id;
  final String name; // Arabic display name

  const Reciter(this.id, this.name);
}

/// Selectable reciters (Husary is the default — first in the list).
const List<Reciter> kReciters = [
  Reciter('Husary_128kbps', 'محمود الحصري'),
  Reciter('Minshawy_Murattal_128kbps', 'محمد صديق المنشاوي'),
  Reciter('Maher_AlMuaiqly_64kbps', 'ماهر المعيقلي'),
  Reciter('Ghamadi_40kbps', 'سعد الغامدي'),
];

const Reciter kDefaultReciter = Reciter('Husary_128kbps', 'محمود الحصري');
