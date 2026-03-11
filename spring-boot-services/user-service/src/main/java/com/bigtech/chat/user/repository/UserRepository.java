package com.bigtech.chat.user.repository;

import com.bigtech.chat.user.entity.User;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 사용자 레포지토리
 */
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    /**
     * 이메일로 사용자 조회
     */
    Optional<User> findByEmail(String email);

    /**
     * 사용자명으로 사용자 조회
     */
    Optional<User> findByUsername(String username);

    /**
     * 이메일 존재 여부 확인
     */
    boolean existsByEmail(String email);

    /**
     * 사용자명 존재 여부 확인
     */
    boolean existsByUsername(String username);

    /**
     * 사용자 검색 (사용자명 또는 표시 이름으로)
     */
    @Query("SELECT u FROM User u WHERE " +
            "(LOWER(u.username) LIKE LOWER(CONCAT('%', :query, '%')) OR " +
            "LOWER(u.displayName) LIKE LOWER(CONCAT('%', :query, '%'))) " +
            "AND u.isActive = true AND u.id != :excludeUserId")
    List<User> searchByUsernameOrDisplayName(
            @Param("query") String query,
            @Param("excludeUserId") Long excludeUserId,
            Pageable pageable
    );

    /**
     * 활성 사용자 조회
     */
    Optional<User> findByIdAndIsActiveTrue(Long id);

    /**
     * 온라인 사용자 수 조회
     */
    long countByIsOnlineTrue();
}
