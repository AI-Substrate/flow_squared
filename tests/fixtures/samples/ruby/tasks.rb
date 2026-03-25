# frozen_string_literal: true

# Database migration and maintenance tasks.
# Provides Rake tasks for common database operations.

require 'rake'
require 'logger'

module DatabaseTasks
  # Configuration for database connections.
  # Reads settings from environment variables with sensible defaults.
  class Config
    attr_accessor :host, :port, :database, :username, :password
    attr_accessor :pool_size, :timeout, :ssl_enabled

    def initialize
      @host = ENV.fetch('DB_HOST', 'localhost')
      @port = ENV.fetch('DB_PORT', 5432).to_i
      @database = ENV.fetch('DB_NAME', 'development')
      @username = ENV.fetch('DB_USER', 'postgres')
      @password = ENV['DB_PASSWORD']
      @pool_size = ENV.fetch('DB_POOL_SIZE', 5).to_i
      @timeout = ENV.fetch('DB_TIMEOUT', 30).to_i
      @ssl_enabled = ENV['DB_SSL'] == 'true'
    end

    def connection_url
      auth = password ? "#{username}:#{password}@" : "#{username}@"
      ssl = ssl_enabled ? '?sslmode=require' : ''
      "postgresql://#{auth}#{host}:#{port}/#{database}#{ssl}"
    end
  end

  # Migration runner with version tracking.
  class MigrationRunner
    attr_reader :config, :logger, :migrations_path

    def initialize(config: nil, migrations_path: 'db/migrate')
      @config = config || Config.new
      @migrations_path = migrations_path
      @logger = Logger.new($stdout)
      @logger.level = Logger::INFO
    end

    # Run all pending migrations.
    #
    # @return [Array<String>] Names of applied migrations.
    def migrate_up
      pending = pending_migrations
      return [] if pending.empty?

      logger.info "Found #{pending.size} pending migration(s)"

      applied = []
      pending.each do |migration|
        apply_migration(migration)
        applied << migration[:name]
        logger.info "Applied: #{migration[:name]}"
      end

      applied
    end

    # Roll back the last N migrations.
    #
    # @param steps [Integer] Number of migrations to roll back.
    # @return [Array<String>] Names of rolled back migrations.
    def rollback(steps = 1)
      applied = applied_migrations.last(steps)
      return [] if applied.empty?

      rolled_back = []
      applied.reverse_each do |migration|
        revert_migration(migration)
        rolled_back << migration[:name]
        logger.info "Reverted: #{migration[:name]}"
      end

      rolled_back
    end

    # Get status of all migrations.
    #
    # @return [Array<Hash>] List of migrations with status.
    def status
      all_migrations.map do |migration|
        {
          version: migration[:version],
          name: migration[:name],
          status: migration_applied?(migration) ? 'up' : 'down'
        }
      end
    end

    private

    def all_migrations
      Dir.glob(File.join(migrations_path, '*.rb')).map do |file|
        name = File.basename(file, '.rb')
        version = name.split('_').first
        { version: version, name: name, file: file }
      end.sort_by { |m| m[:version] }
    end

    def pending_migrations
      all_migrations.reject { |m| migration_applied?(m) }
    end

    def applied_migrations
      all_migrations.select { |m| migration_applied?(m) }
    end

    def migration_applied?(migration)
      # Check schema_migrations table
      false # Placeholder
    end

    def apply_migration(migration)
      # Load and execute migration
    end

    def revert_migration(migration)
      # Load and revert migration
    end
  end

  # Database seeder for development data.
  class Seeder
    attr_reader :config, :logger

    def initialize(config: nil)
      @config = config || Config.new
      @logger = Logger.new($stdout)
    end

    # Seed the database with initial data.
    #
    # @param environment [Symbol] Target environment.
    # @yield [seeder] Block to define seed data.
    def seed(environment = :development)
      logger.info "Seeding database for #{environment}"

      yield self if block_given?

      logger.info 'Seeding complete'
    end

    # Create records if they don't exist.
    #
    # @param table [Symbol] Table name.
    # @param records [Array<Hash>] Records to create.
    # @param unique_by [Symbol, Array<Symbol>] Unique constraint columns.
    def create_unless_exists(table, records, unique_by:)
      records.each do |record|
        # Upsert logic
        logger.debug "Seeding #{table}: #{record[unique_by]}"
      end
    end
  end
end

# Rake task definitions
namespace :db do
  desc 'Run all pending database migrations'
  task :migrate do
    runner = DatabaseTasks::MigrationRunner.new
    applied = runner.migrate_up

    if applied.empty?
      puts 'No pending migrations'
    else
      puts "Applied #{applied.size} migration(s)"
    end
  end

  desc 'Roll back the last migration'
  task :rollback, [:steps] do |_t, args|
    steps = (args[:steps] || 1).to_i
    runner = DatabaseTasks::MigrationRunner.new
    rolled_back = runner.rollback(steps)

    if rolled_back.empty?
      puts 'Nothing to roll back'
    else
      puts "Rolled back #{rolled_back.size} migration(s)"
    end
  end

  desc 'Show migration status'
  task :status do
    runner = DatabaseTasks::MigrationRunner.new
    status = runner.status

    puts "\nMigration Status:\n"
    puts '=' * 60

    status.each do |m|
      status_mark = m[:status] == 'up' ? '[x]' : '[ ]'
      puts "#{status_mark} #{m[:version]} #{m[:name]}"
    end
  end

  desc 'Seed the database with initial data'
  task :seed, [:environment] do |_t, args|
    env = (args[:environment] || 'development').to_sym
    seeder = DatabaseTasks::Seeder.new

    seeder.seed(env) do |s|
      # Define seed data here
      s.create_unless_exists(:users, [
        { email: 'admin@example.com', role: 'admin' },
        { email: 'user@example.com', role: 'user' }
      ], unique_by: :email)
    end
  end

  desc 'Reset the database (drop, create, migrate, seed)'
  task :reset => [:drop, :create, :migrate, :seed]

  desc 'Drop the database'
  task :drop do
    config = DatabaseTasks::Config.new
    puts "Dropping database: #{config.database}"
    # Drop database logic
  end

  desc 'Create the database'
  task :create do
    config = DatabaseTasks::Config.new
    puts "Creating database: #{config.database}"
    # Create database logic
  end
end
