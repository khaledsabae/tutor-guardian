/// The wall clock, as a provider — so a test can stand «اليوم» on a Friday or
/// a Monday without waiting for one.
///
/// Only what decides a day-of-week moment reads it (Noor's line, the Monday
/// reveal of the week's plan, Friday's harvest); everything else keeps
/// calling `DateTime.now()`.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);
