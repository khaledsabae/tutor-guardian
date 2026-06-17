/// Entry screen for the Emotion Maze mini-game.
library;

import 'package:flutter/material.dart';
import 'emotion_maze_game.dart';

class EmotionMazeGameScreen extends StatelessWidget {
  const EmotionMazeGameScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const EmotionMazeGame();
  }
}
