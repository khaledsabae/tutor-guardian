/// Data Transfer Objects matching the v1 contract in `MOBILE_API.md`.
///
/// All classes use additive decoding — unknown fields are silently ignored,
/// which is required by contract section 8 ("additive fields may appear").
library;

import 'enums.dart';

/// Reply returned by `/api/assistant/{query,stream,draft}` (also the
/// payload of the `event: done` SSE frame).
class AssistantReply {
  final String replyText;
  final Domain domain;
  final Severity severity;
  final bool needsHumanReview;
  final EscalationTarget escalationTarget;
  final ReplyMode mode;
  final String? sessionId;
  final Map<String, dynamic>? metadata;

  const AssistantReply({
    required this.replyText,
    required this.domain,
    required this.severity,
    required this.needsHumanReview,
    required this.escalationTarget,
    required this.mode,
    required this.sessionId,
    this.metadata,
  });

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      replyText: (json['reply_text'] ?? '') as String,
      domain: Domain.fromWire(json['domain'] as String?),
      severity: Severity.fromWire(json['severity'] as String?),
      needsHumanReview: (json['needs_human_review'] ?? false) as bool,
      escalationTarget:
          EscalationTarget.fromWire(json['escalation_target']),
      mode: ReplyMode.fromWire(json['mode'] as String?),
      sessionId: json['session_id'] as String?,
      metadata: json['metadata'] is Map
          ? Map<String, dynamic>.from(json['metadata'] as Map)
          : null,
    );
  }

  /// True when the server signalled an out-of-scope / banned request.
  bool get isBanned => mode == ReplyMode.banned;

  /// True when the server returned a full safety escalation reply.
  bool get isEmergency =>
      mode == ReplyMode.emergency ||
      escalationTarget == EscalationTarget.emergencyServices;
}

/// Response from `POST /api/chat/sessions`.
class SessionResponse {
  final String sessionId;
  final String token;

  const SessionResponse({required this.sessionId, required this.token});

  factory SessionResponse.fromJson(Map<String, dynamic> json) {
    return SessionResponse(
      sessionId: json['session_id'] as String,
      token: json['token'] as String,
    );
  }
}

/// One message inside `SessionResponse.messages[]` and inside history
/// rehydration responses.
class ChatMessage {
  final String role; // "user" | "assistant"
  final String content;
  final Domain? domain;
  final Severity? severity;
  final ReplyMode? mode;
  final bool needsHumanReview;
  final DateTime? createdAt;

  const ChatMessage({
    required this.role,
    required this.content,
    this.domain,
    this.severity,
    this.mode,
    this.needsHumanReview = false,
    this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    DateTime? parseDate(Object? v) {
      if (v is String && v.isNotEmpty) {
        return DateTime.tryParse(v);
      }
      return null;
    }

    return ChatMessage(
      role: (json['role'] ?? 'user') as String,
      content: (json['content'] ?? '') as String,
      domain: json['domain'] is String
          ? Domain.fromWire(json['domain'] as String)
          : null,
      severity: json['severity'] is String
          ? Severity.fromWire(json['severity'] as String)
          : null,
      mode: json['mode'] is String
          ? ReplyMode.fromWire(json['mode'] as String)
          : null,
      needsHumanReview: (json['needs_human_review'] ?? false) as bool,
      createdAt: parseDate(json['created_at']),
    );
  }
}

/// Response from `GET /api/chat/sessions/{id}`.
class SessionHistory {
  final String id;
  final String? deviceId;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final Map<String, dynamic> metadata;
  final List<ChatMessage> messages;

  const SessionHistory({
    required this.id,
    this.deviceId,
    this.createdAt,
    this.updatedAt,
    this.metadata = const {},
    required this.messages,
  });

  factory SessionHistory.fromJson(Map<String, dynamic> json) {
    DateTime? parseDate(Object? v) {
      if (v is String && v.isNotEmpty) return DateTime.tryParse(v);
      return null;
    }

    final rawMsgs = (json['messages'] as List?) ?? const [];
    return SessionHistory(
      id: json['id'] as String,
      deviceId: json['device_id'] as String?,
      createdAt: parseDate(json['created_at']),
      updatedAt: parseDate(json['updated_at']),
      metadata: json['metadata'] is Map
          ? Map<String, dynamic>.from(json['metadata'] as Map)
          : const {},
      messages: rawMsgs
          .whereType<Map<String, dynamic>>()
          .map(ChatMessage.fromJson)
          .toList(),
    );
  }
}

/// Request body for `/api/assistant/{query,stream}`.
class AssistantQuery {
  final AgeGroup ageGroup;
  final Severity severity;
  final String? behaviorType;
  final String messageText;
  final String? sessionId;

  const AssistantQuery({
    required this.ageGroup,
    required this.severity,
    required this.messageText,
    this.behaviorType,
    this.sessionId,
  });

  Map<String, dynamic> toJson() => {
        'age_group': ageGroup.wire,
        'severity': severity.wire,
        if (behaviorType != null && behaviorType!.isNotEmpty)
          'behavior_type': behaviorType,
        'message_text': messageText,
        if (sessionId != null) 'session_id': sessionId,
      };
}
