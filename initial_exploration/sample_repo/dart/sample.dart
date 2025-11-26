/// Sample Dart file for tree-sitter exploration.
/// Includes Flutter-style patterns and modern Dart features.

import 'dart:async';
import 'dart:convert';

// Type alias
typedef JsonMap = Map<String, dynamic>;
typedef Callback<T> = void Function(T value);

// Enum with enhanced features (Dart 2.17+)
enum Status {
  pending('Pending'),
  active('Active'),
  inactive('Inactive');

  const Status(this.label);
  final String label;

  bool get isTerminal => this == inactive;
}

// Abstract class (interface)
abstract class Repository<T> {
  Future<T?> find(String id);
  Future<void> save(T item);
  Future<bool> delete(String id);
}

// Mixin
mixin Timestamped {
  DateTime? createdAt;
  DateTime? updatedAt;

  void touch() {
    updatedAt = DateTime.now();
  }
}

mixin Identifiable {
  String get id;
}

// Class with mixins
class User with Timestamped, Identifiable {
  @override
  final String id;
  String name;
  String? email;
  Status _status = Status.pending;

  // Constructor with initializer list
  User({
    required this.id,
    required this.name,
    this.email,
  }) : createdAt = DateTime.now();

  // Named constructor
  User.guest() : this(id: 'guest', name: 'Guest User');

  // Factory constructor
  factory User.fromJson(JsonMap json) {
    return User(
      id: json['id'] as String,
      name: json['name'] as String,
      email: json['email'] as String?,
    );
  }

  // Getter
  Status get status => _status;

  // Setter with validation
  set status(Status value) {
    if (_status.isTerminal) {
      throw StateError('Cannot change terminal status');
    }
    _status = value;
    touch();
  }

  // Method
  JsonMap toJson() => {
        'id': id,
        'name': name,
        'email': email,
        'status': status.name,
      };

  // Async method
  Future<void> activate() async {
    await Future.delayed(const Duration(milliseconds: 100));
    status = Status.active;
  }

  // Operator override
  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is User && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'User(id: $id, name: $name)';
}

// Extension
extension UserExtension on User {
  String get displayName => '$name ($id)';

  bool get hasEmail => email != null && email!.isNotEmpty;
}

// Extension on built-in type
extension StringExtension on String {
  String capitalize() =>
      isEmpty ? this : '${this[0].toUpperCase()}${substring(1)}';
}

// Generic class
class InMemoryRepository<T extends Identifiable> implements Repository<T> {
  final Map<String, T> _items = {};

  @override
  Future<T?> find(String id) async {
    return _items[id];
  }

  @override
  Future<void> save(T item) async {
    _items[item.id] = item;
  }

  @override
  Future<bool> delete(String id) async {
    return _items.remove(id) != null;
  }

  // Stream
  Stream<T> watchAll() async* {
    for (final item in _items.values) {
      yield item;
    }
  }
}

// Abstract class with implementation
abstract class BaseService<T extends Identifiable> {
  final Repository<T> repository;

  BaseService(this.repository);

  Future<T?> getById(String id) => repository.find(id);

  // Abstract method
  bool validate(T item);
}

// Concrete service
class UserService extends BaseService<User> {
  UserService(Repository<User> repository) : super(repository);

  @override
  bool validate(User item) => item.name.isNotEmpty;

  // Null-aware cascade
  Future<User> createUser(String name, {String? email}) async {
    final user = User(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      name: name,
    )..email = email;

    await repository.save(user);
    return user;
  }
}

// Sealed class (Dart 3.0+)
sealed class Result<T> {
  const Result();
}

class Success<T> extends Result<T> {
  final T value;
  const Success(this.value);
}

class Failure<T> extends Result<T> {
  final String error;
  const Failure(this.error);
}

// Pattern matching (Dart 3.0+)
String handleResult(Result<User> result) {
  return switch (result) {
    Success(value: final user) => 'Found: ${user.name}',
    Failure(error: final msg) => 'Error: $msg',
  };
}

// Record type (Dart 3.0+)
typedef UserRecord = ({String id, String name, String? email});

UserRecord toRecord(User user) => (id: user.id, name: user.name, email: user.email);

// Top-level function
Future<void> main() async {
  final repo = InMemoryRepository<User>();
  final service = UserService(repo);

  // Cascade notation
  final user = await service.createUser('Alice')
    ..email = 'alice@example.com'
    ..status = Status.active;

  print(user.displayName);
  print('Capitalized: ${'hello'.capitalize()}');

  // Collection literals with spread
  final users = [user];
  final moreUsers = [...users, User.guest()];

  // Collection if/for
  final activeUsers = [
    for (final u in moreUsers)
      if (u.status == Status.active) u
  ];

  // Null-aware operators
  final email = user.email ?? 'no-email';
  final length = user.email?.length ?? 0;

  print('Active users: ${activeUsers.length}');
}
